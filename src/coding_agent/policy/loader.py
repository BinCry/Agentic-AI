"""Strict non-executable TOML policy loading."""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

from ..storage.workspace import WorkspacePaths
from ..tools.contracts import ToolRisk
from .models import ApprovalMode, PolicyAction, PolicyLayer, PolicyRule, WorkspaceTrust


class PolicyConfigurationError(ValueError):
    """Raised when a policy file is invalid or attempts to widen workspace authority."""


class PolicyLoader:
    _top_keys = {"version", "rules"}
    _rule_keys = {
        "id", "action", "reason_code", "tool", "tool_prefix", "effects", "modes",
        "workspace_trust", "argument_equals", "command_prefix",
    }

    def __init__(self, paths: WorkspacePaths, *, maximum_bytes: int = 262_144) -> None:
        if not isinstance(maximum_bytes, int) or isinstance(maximum_bytes, bool) or maximum_bytes < 1:
            raise ValueError("maximum policy bytes must be positive")
        if not paths.workspace_root.is_dir():
            raise PolicyConfigurationError("policy workspace does not exist")
        self.paths = paths
        self.maximum_bytes = maximum_bytes

    def load_explicit(self, path: str | Path) -> tuple[PolicyRule, ...]:
        resolved = self.paths.resolve_readonly_path(path, must_exist=True)
        return self._load(resolved, PolicyLayer.TRUSTED, narrowing=False)

    def load_workspace_narrowing(self, path: str | Path) -> tuple[PolicyRule, ...]:
        resolved = self.paths.resolve_workspace_path(path, must_exist=True)
        return self._load(resolved, PolicyLayer.WORKSPACE, narrowing=True)

    def _load(self, path: Path, layer: PolicyLayer, *, narrowing: bool) -> tuple[PolicyRule, ...]:
        try:
            if not path.is_file() or path.stat().st_size > self.maximum_bytes:
                raise PolicyConfigurationError("policy file is missing or exceeds byte limit")
            with path.open("rb") as handle:
                payload = tomllib.load(handle)
        except (OSError, tomllib.TOMLDecodeError) as exc:
            raise PolicyConfigurationError(f"invalid policy TOML: {type(exc).__name__}") from exc
        unknown_top = set(payload) - self._top_keys
        rules = payload.get("rules")
        version = payload.get("version")
        if (
            unknown_top
            or not isinstance(version, int)
            or isinstance(version, bool)
            or version != 1
            or not isinstance(rules, list)
        ):
            raise PolicyConfigurationError("policy requires version 1, rules, and no unknown keys")
        parsed = tuple(self._parse_rule(item, layer) for item in rules)
        ids = [item.id for item in parsed]
        if len(ids) != len(set(ids)):
            raise PolicyConfigurationError("policy rule ids must be unique")
        if narrowing and any(item.action is not PolicyAction.DENY for item in parsed):
            raise PolicyConfigurationError("workspace policy may contain only deny rules")
        return parsed

    def _parse_rule(self, payload: object, layer: PolicyLayer) -> PolicyRule:
        if not isinstance(payload, dict):
            raise PolicyConfigurationError("policy rule must be an object")
        unknown = set(payload) - self._rule_keys
        if unknown:
            raise PolicyConfigurationError(f"unknown rule keys: {sorted(unknown)}")
        try:
            arguments = payload.get("argument_equals", {})
            if not isinstance(arguments, dict):
                raise ValueError("argument_equals must be an object")
            return PolicyRule(
                id=_required_text(payload, "id"),
                layer=layer,
                action=PolicyAction(_required_text(payload, "action")),
                reason_code=_required_text(payload, "reason_code"),
                tool=_optional_text(payload, "tool"),
                tool_prefix=_optional_text(payload, "tool_prefix"),
                effects=frozenset(ToolRisk(item) for item in _string_list(payload, "effects")),
                modes=frozenset(ApprovalMode(item) for item in _string_list(payload, "modes")),
                workspace_trust=frozenset(
                    WorkspaceTrust(item) for item in _string_list(payload, "workspace_trust")
                ),
                argument_equals=tuple(sorted(arguments.items())),
                command_prefix=tuple(_string_list(payload, "command_prefix")),
            )
        except (TypeError, ValueError) as exc:
            raise PolicyConfigurationError(f"invalid policy rule: {exc}") from exc


def _required_text(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{key} must be a non-empty string")
    return value


def _optional_text(payload: dict[str, Any], key: str) -> str | None:
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise ValueError(f"{key} must be a non-empty string")
    return value


def _string_list(payload: dict[str, Any], key: str) -> list[str]:
    value = payload.get(key, [])
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
        raise ValueError(f"{key} must be a list of non-empty strings")
    return value
