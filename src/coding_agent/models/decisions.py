"""Validated structured outputs used for important model decisions."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .validation import (
    ModelValidationError,
    require_boolean,
    require_choice,
    require_mapping,
    require_string,
    require_string_list,
)


@dataclass(slots=True)
class IssueAnalysis:
    task_type: str
    problem: str
    expected_behavior: str
    acceptance_criteria: list[str]
    search_queries: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "IssueAnalysis":
        data = require_mapping(payload)
        return cls(
            task_type=require_choice(
                data,
                "task_type",
                {"analysis", "bug_fix", "feature", "refactor", "test"},
            ),
            problem=require_string(data, "problem"),
            expected_behavior=require_string(data, "expected_behavior"),
            acceptance_criteria=require_string_list(data, "acceptance_criteria", allow_empty=False),
            search_queries=require_string_list(data, "search_queries"),
            risks=require_string_list(data, "risks"),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ImplementationStep:
    id: str
    action: str
    file: str
    description: str
    dependencies: list[str] = field(default_factory=list)
    verification_method: str = "run configured tests and review the final diff"

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ImplementationStep":
        data = require_mapping(payload, "step")
        return cls(
            id=require_string(data, "id"),
            action=require_choice(data, "action", {"read", "modify", "create", "test"}),
            file=require_string(data, "file"),
            description=require_string(data, "description"),
            dependencies=require_string_list(data, "dependencies"),
            verification_method=require_string(
                data,
                "verification_method",
                allow_empty=False,
            )
            if "verification_method" in data
            else "run configured tests and review the final diff",
        )


@dataclass(slots=True)
class ImplementationPlan:
    objective: str
    steps: list[ImplementationStep]
    evidence_citations: list[str] = field(default_factory=list)
    expected_tests: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ImplementationPlan":
        data = require_mapping(payload)
        raw_steps = data.get("steps")
        if not isinstance(raw_steps, list) or not raw_steps:
            raise ModelValidationError(["steps must be a non-empty list"])
        steps = [ImplementationStep.from_dict(step) for step in raw_steps]
        step_ids = [step.id for step in steps]
        if len(step_ids) != len(set(step_ids)):
            raise ModelValidationError(["step ids must be unique"])
        seen: set[str] = set()
        for step in steps:
            unknown = set(step.dependencies) - seen
            if unknown:
                raise ModelValidationError(
                    [f"step {step.id} has unresolved or forward dependencies: {sorted(unknown)}"]
                )
            seen.add(step.id)
        return cls(
            objective=require_string(data, "objective"),
            steps=steps,
            evidence_citations=require_string_list(data, "evidence_citations"),
            expected_tests=require_string_list(data, "expected_tests"),
            risks=require_string_list(data, "risks"),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ToolDecision:
    tool_name: str
    arguments: dict[str, Any]
    rationale: str
    requires_approval: bool

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ToolDecision":
        data = require_mapping(payload)
        arguments = data.get("arguments")
        if not isinstance(arguments, dict):
            raise ModelValidationError(["arguments must be an object"])
        return cls(
            tool_name=require_string(data, "tool_name"),
            arguments=arguments,
            rationale=require_string(data, "rationale"),
            requires_approval=require_boolean(data, "requires_approval"),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class DebugDecision:
    root_cause: str
    evidence: list[str]
    next_action: str
    rationale: str
    search_queries: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "DebugDecision":
        data = require_mapping(payload)
        return cls(
            root_cause=require_string(data, "root_cause"),
            evidence=require_string_list(data, "evidence", allow_empty=False),
            next_action=require_choice(data, "next_action", {"edit", "retrieve", "fail"}),
            rationale=require_string(data, "rationale"),
            search_queries=require_string_list(data, "search_queries"),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ReviewFinding:
    severity: str
    finding_type: str
    file: str
    line: int | None
    description: str
    suggested_fix: str

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ReviewFinding":
        data = require_mapping(payload, "finding")
        line = data.get("line")
        if line is not None and (not isinstance(line, int) or line < 1):
            raise ModelValidationError(["line must be a positive integer or null"])
        return cls(
            severity=require_choice(data, "severity", {"low", "medium", "high", "critical"}),
            finding_type=require_string(data, "finding_type"),
            file=require_string(data, "file"),
            line=line,
            description=require_string(data, "description"),
            suggested_fix=require_string(data, "suggested_fix"),
        )


@dataclass(slots=True)
class ReviewResult:
    approved: bool
    findings: list[ReviewFinding]
    summary: str

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ReviewResult":
        data = require_mapping(payload)
        raw_findings = data.get("findings", [])
        if not isinstance(raw_findings, list):
            raise ModelValidationError(["findings must be a list"])
        findings = [ReviewFinding.from_dict(item) for item in raw_findings]
        approved = require_boolean(data, "approved")
        if approved and any(item.severity in {"high", "critical"} for item in findings):
            raise ModelValidationError(["approved review cannot contain high or critical findings"])
        return cls(approved=approved, findings=findings, summary=require_string(data, "summary"))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class AnalysisCompletionResult:
    status: str
    summary: str
    reasoning: str
    citations: list[str]
    unresolved_findings: list[str]

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "AnalysisCompletionResult":
        data = require_mapping(payload)
        status = require_choice(data, "status", {"completed", "failed"})
        citations = require_string_list(data, "citations")
        if status == "completed" and not citations:
            raise ModelValidationError(["completed analysis requires citations"])
        return cls(
            status=status,
            summary=require_string(data, "summary"),
            reasoning=require_string(data, "reasoning"),
            citations=citations,
            unresolved_findings=require_string_list(data, "unresolved_findings"),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class TaskCompletionResult:
    status: str
    summary: str
    reasoning: str
    modified_files: list[str]
    tests_passed: bool
    citations: list[str]
    unresolved_findings: list[str]
    pr_summary: str = ""

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "TaskCompletionResult":
        data = require_mapping(payload)
        status = require_choice(data, "status", {"completed", "failed"})
        tests_passed = require_boolean(data, "tests_passed")
        unresolved = require_string_list(data, "unresolved_findings")
        modified_files = require_string_list(data, "modified_files")
        citations = require_string_list(data, "citations")
        if status == "completed" and not tests_passed:
            raise ModelValidationError(["completed result requires passing tests"])
        if status == "completed" and not modified_files:
            raise ModelValidationError(["completed result requires modified files"])
        if status == "completed" and not citations:
            raise ModelValidationError(["completed result requires citations"])
        return cls(
            status=status,
            summary=require_string(data, "summary"),
            reasoning=require_string(data, "reasoning"),
            modified_files=modified_files,
            tests_passed=tests_passed,
            citations=citations,
            unresolved_findings=unresolved,
            pr_summary=(data.get("pr_summary", "") if isinstance(data.get("pr_summary", ""), str) else ""),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
