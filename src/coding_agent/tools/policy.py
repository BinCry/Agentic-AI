"""Deny-by-default permission policy for controlled repository tools."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

from ..policy.engine import PolicyEngine
from ..policy.models import (
    ApprovalMode,
    PolicyAction,
    PolicyDecision as ExplainedPolicyDecision,
    PolicyInput,
    PolicyRule,
    WorkspaceTrust,
)
from ..storage.workspace import WorkspacePaths, WorkspacePolicyError
from .contracts import ToolCategory, ToolRequest, ToolRisk, ToolSpec


class ToolPolicyError(ValueError):
    """Raised when a tool request violates the Phase 2 policy."""


class UnknownToolError(ToolPolicyError):
    """Raised for a tool outside the explicit tool surface."""


class ToolStateError(ToolPolicyError):
    """Raised when a tool is requested in an unsafe workflow state."""


class ToolArgumentError(ToolPolicyError):
    """Raised when a tool argument is malformed or unsafe."""


class ToolAccessError(ToolArgumentError):
    """Raised when a tool path violates the workspace access boundary."""


@dataclass(slots=True, frozen=True)
class PolicyDecision:
    spec: ToolSpec
    requires_approval: bool
    normalized_arguments: dict[str, Any]
    explanation: ExplainedPolicyDecision


READ_STATES = frozenset(
    {
        "ANALYZING",
        "RETRIEVING",
        "PLANNING",
        "EDITING",
        "TESTING",
        "DEBUGGING",
        "REVIEWING",
        "FINALIZING",
    }
)
EDIT_STATES = frozenset({"EDITING", "DEBUGGING"})
TEST_STATES = frozenset({"TESTING", "DEBUGGING"})


DEFAULT_TOOL_SPECS = (
    ToolSpec("repo.list_files", ToolCategory.READ, True, False, READ_STATES),
    ToolSpec("repo.read_file", ToolCategory.READ, True, False, READ_STATES),
    ToolSpec("repo.search_text", ToolCategory.READ, True, False, READ_STATES),
    ToolSpec("repo.find_symbols", ToolCategory.READ, True, False, READ_STATES),
    ToolSpec("repo.retrieve", ToolCategory.READ, True, False, READ_STATES),
    ToolSpec(
        "repo.apply_patch",
        ToolCategory.MUTATION,
        False,
        True,
        EDIT_STATES,
        risks=frozenset({ToolRisk.WORKSPACE_WRITE}),
    ),
    ToolSpec(
        "repo.create_file",
        ToolCategory.MUTATION,
        False,
        True,
        EDIT_STATES,
        risks=frozenset({ToolRisk.WORKSPACE_WRITE}),
    ),
    ToolSpec("test.detect_framework", ToolCategory.READ, True, False, READ_STATES),
    ToolSpec(
        "test.run",
        ToolCategory.TEST,
        False,
        True,
        TEST_STATES,
        timeout_seconds=60.0,
        risks=frozenset({ToolRisk.PROCESS, ToolRisk.WORKSPACE_WRITE}),
    ),
    ToolSpec("git.status", ToolCategory.GIT, True, False, READ_STATES),
    ToolSpec("git.diff", ToolCategory.GIT, True, False, READ_STATES),
    ToolSpec("git.changed_files", ToolCategory.GIT, True, False, READ_STATES),
)


class ToolPermissionPolicy:
    """Validate tool identity, workflow state and every repository path."""

    def __init__(
        self,
        paths: WorkspacePaths,
        specs: tuple[ToolSpec, ...] = DEFAULT_TOOL_SPECS,
        *,
        mode: ApprovalMode = ApprovalMode.ASK,
        workspace_trust: WorkspaceTrust = WorkspaceTrust.TRUSTED,
        rules: tuple[PolicyRule, ...] = (),
    ) -> None:
        self.paths = paths
        self._specs = {spec.name: spec for spec in specs}
        self.mode = mode
        self.workspace_trust = workspace_trust
        self.engine = PolicyEngine(rules)

    def spec(self, tool_name: str) -> ToolSpec:
        try:
            return self._specs[tool_name]
        except KeyError as exc:
            raise UnknownToolError(f"tool is not allowlisted: {tool_name}") from exc

    def evaluate(self, request: ToolRequest) -> PolicyDecision:
        decision = self.explain(request)
        if decision.explanation.action is PolicyAction.DENY:
            explanation = decision.explanation
            raise ToolAccessError(
                f"policy denied {decision.spec.name}: {explanation.reason_code} "
                f"({explanation.rule_id})"
            )
        return decision

    def explain(self, request: ToolRequest) -> PolicyDecision:
        spec = self.spec(request.tool_name)
        if request.workflow_state not in spec.allowed_states:
            raise ToolStateError(
                f"tool {spec.name} is not allowed in workflow state {request.workflow_state}"
            )
        if not isinstance(request.arguments, dict):
            raise ToolArgumentError("tool arguments must be an object")
        normalized = dict(request.arguments)
        self._validate_arguments(spec.name, normalized)
        self._validate_paths(spec, normalized)
        explanation = self.engine.evaluate(
            PolicyInput(
                spec.name,
                normalized,
                request.workflow_state,
                spec.risks,
                self.mode,
                self.workspace_trust,
            )
        )
        if (
            spec.requires_approval
            and spec.risks == frozenset({ToolRisk.READ})
            and explanation.action is PolicyAction.ALLOW
        ):
            explanation = PolicyEngine(
                (
                    PolicyRule(
                        f"compat.{spec.name}",
                        layer=explanation.layer,
                        action=PolicyAction.ASK,
                        reason_code="LEGACY_APPROVAL_REQUIRED",
                        tool=spec.name,
                    ),
                )
            ).evaluate(
                PolicyInput(
                    spec.name,
                    normalized,
                    request.workflow_state,
                    spec.risks,
                    self.mode,
                    self.workspace_trust,
                )
            )
        return PolicyDecision(
            spec,
            explanation.action is PolicyAction.ASK,
            normalized,
            explanation,
        )

    def _validate_arguments(self, tool_name: str, arguments: dict[str, Any]) -> None:
        allowed: dict[str, set[str]] = {
            "repo.list_files": {"path", "maximum_files"},
            "repo.read_file": {"path"},
            "repo.search_text": {"query", "path", "regular_expression", "maximum_matches"},
            "repo.find_symbols": {"path"},
            "repo.retrieve": {"query", "top_k"},
            "repo.apply_patch": {"path", "patch", "expected_sha256"},
            "repo.create_file": {"path", "content"},
            "test.detect_framework": set(),
            "test.run": {"profile"},
            "git.status": set(),
            "git.diff": {"paths"},
            "git.changed_files": set(),
        }
        unknown = set(arguments) - allowed[tool_name]
        if unknown:
            raise ToolArgumentError(f"unexpected arguments for {tool_name}: {sorted(unknown)}")
        required: dict[str, tuple[str, ...]] = {
            "repo.list_files": (),
            "repo.read_file": ("path",),
            "repo.search_text": ("query",),
            "repo.find_symbols": ("path",),
            "repo.retrieve": ("query",),
            "repo.apply_patch": ("path", "patch", "expected_sha256"),
            "repo.create_file": ("path", "content"),
            "test.detect_framework": (),
            "test.run": ("profile",),
            "git.status": (),
            "git.diff": (),
            "git.changed_files": (),
        }
        missing = [key for key in required[tool_name] if key not in arguments]
        if missing:
            raise ToolArgumentError(f"missing required arguments: {missing}")
        for key in ("path", "query", "patch", "expected_sha256", "content", "profile"):
            if key in arguments and (not isinstance(arguments[key], str) or not arguments[key]):
                raise ToolArgumentError(f"{key} must be a non-empty string")
        if "regular_expression" in arguments and not isinstance(arguments["regular_expression"], bool):
            raise ToolArgumentError("regular_expression must be boolean")
        if "maximum_matches" in arguments:
            value = arguments["maximum_matches"]
            if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 200:
                raise ToolArgumentError("maximum_matches must be an integer between 1 and 200")
        if "maximum_files" in arguments:
            value = arguments["maximum_files"]
            if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 2_000:
                raise ToolArgumentError("maximum_files must be an integer between 1 and 2000")
        if "top_k" in arguments:
            value = arguments["top_k"]
            if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 100:
                raise ToolArgumentError("top_k must be an integer between 1 and 100")
        if "expected_sha256" in arguments and not re.fullmatch(r"[0-9a-fA-F]{64}", arguments["expected_sha256"]):
            raise ToolArgumentError("expected_sha256 must be a SHA-256 hex digest")
        if "paths" in arguments:
            paths = arguments["paths"]
            if not isinstance(paths, list) or any(not isinstance(item, str) or not item for item in paths):
                raise ToolArgumentError("paths must be a list of non-empty strings")

    def _validate_paths(self, spec: ToolSpec, arguments: dict[str, Any]) -> None:
        candidates: list[tuple[str, bool]] = []
        for key in ("path", "target"):
            if key in arguments:
                candidates.append((arguments[key], spec.category is ToolCategory.READ))
        paths = arguments.get("paths")
        if paths is not None:
            if not isinstance(paths, list) or any(not isinstance(item, str) for item in paths):
                raise ToolArgumentError("paths must be a list of strings")
            candidates.extend((item, spec.category is ToolCategory.READ) for item in paths)
        for value, must_exist in candidates:
            if not isinstance(value, str) or not value.strip():
                raise ToolArgumentError("path arguments must be non-empty strings")
            try:
                self.paths.resolve_workspace_path(value, must_exist=must_exist)
            except WorkspacePolicyError as exc:
                raise ToolAccessError(str(exc)) from exc
