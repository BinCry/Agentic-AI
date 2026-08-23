"""Prompt-facing JSON schemas for every structured workflow decision."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


def _string(description: str) -> dict[str, Any]:
    return {"type": "string", "minLength": 1, "description": description}


def _string_list(description: str, *, minimum: int = 0) -> dict[str, Any]:
    schema: dict[str, Any] = {
        "type": "array",
        "items": {"type": "string", "minLength": 1},
        "description": description,
    }
    if minimum:
        schema["minItems"] = minimum
    return schema


def _object(
    properties: dict[str, Any],
    required: list[str],
    *,
    description: str,
) -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "description": description,
        "properties": properties,
        "required": required,
    }


_STEP_SCHEMA = _object(
    {
        "id": _string("Stable unique step identifier."),
        "action": {
            "type": "string",
            "enum": ["read", "modify", "create", "test"],
            "description": "One bounded workflow action.",
        },
        "file": _string("Exact repository-relative path or test target."),
        "description": _string("Concrete action grounded in repository evidence."),
        "dependencies": _string_list(
            "Earlier step identifiers that must complete before this step."
        ),
        "verification_method": _string("How this step will be verified."),
    },
    ["id", "action", "file", "description", "dependencies", "verification_method"],
    description="One ordered implementation step; dependencies may reference only earlier steps.",
)


_FINDING_SCHEMA = _object(
    {
        "severity": {
            "type": "string",
            "enum": ["low", "medium", "high", "critical"],
        },
        "finding_type": _string("Finding category such as correctness or security."),
        "file": _string("Exact repository-relative path."),
        "line": {
            "type": ["integer", "null"],
            "minimum": 1,
            "description": "One-based line number when known, otherwise null.",
        },
        "description": _string("Evidence-based description of the finding."),
        "suggested_fix": _string("Minimal correction for the finding."),
    },
    ["severity", "finding_type", "file", "line", "description", "suggested_fix"],
    description="One review finding.",
)


_DECISION_SCHEMAS: dict[str, dict[str, Any]] = {
    "IssueAnalysis": _object(
        {
            "task_type": {
                "type": "string",
                "enum": ["analysis", "bug_fix", "feature", "refactor", "test"],
                "description": (
                    "Use analysis only when the user explicitly requests a read-only explanation, "
                    "inspection, or investigation with no repository changes."
                ),
            },
            "problem": _string("Normalized problem statement."),
            "expected_behavior": _string("Observable successful outcome."),
            "acceptance_criteria": _string_list(
                "Concrete criteria that prove the outcome.", minimum=1
            ),
            "search_queries": _string_list(
                "Up to four concise repository retrieval queries."
            ),
            "risks": _string_list("Material risks, or an empty list when none."),
        },
        [
            "task_type",
            "problem",
            "expected_behavior",
            "acceptance_criteria",
            "search_queries",
            "risks",
        ],
        description="Classify and normalize the user issue before repository retrieval.",
    ),
    "ImplementationPlan": _object(
        {
            "objective": _string("Grounded implementation objective."),
            "steps": {
                "type": "array",
                "minItems": 1,
                "items": _STEP_SCHEMA,
                "description": "Ordered, dependency-safe implementation steps.",
            },
            "evidence_citations": _string_list("Repository evidence citations used by the plan."),
            "expected_tests": _string_list("Allowlisted test profile names expected to run."),
            "risks": _string_list("Implementation risks, or an empty list when none."),
        },
        ["objective", "steps", "evidence_citations", "expected_tests", "risks"],
        description="Minimal repository-grounded implementation plan.",
    ),
    "ToolDecision": _object(
        {
            "tool_name": _string("Exact allowlisted tool name for the current plan step."),
            "arguments": {
                "type": "object",
                "description": "Arguments accepted by the selected tool.",
            },
            "rationale": _string("Why this tool call satisfies the current plan step."),
            "requires_approval": {
                "type": "boolean",
                "description": "Whether the action is mutation- or policy-gated.",
            },
        },
        ["tool_name", "arguments", "rationale", "requires_approval"],
        description="One controlled tool request.",
    ),
    "DebugDecision": _object(
        {
            "root_cause": _string("Evidence-backed root cause."),
            "evidence": _string_list("Concrete failure evidence.", minimum=1),
            "next_action": {"type": "string", "enum": ["edit", "retrieve", "fail"]},
            "rationale": _string("Why the next action follows from the evidence."),
            "search_queries": _string_list("Queries needed when the next action is retrieve."),
        },
        ["root_cause", "evidence", "next_action", "rationale", "search_queries"],
        description="Bounded debugging decision after a failed test or tool action.",
    ),
    "ReviewResult": _object(
        {
            "approved": {"type": "boolean"},
            "findings": {"type": "array", "items": _FINDING_SCHEMA},
            "summary": _string("Concise evidence-based review outcome."),
        },
        ["approved", "findings", "summary"],
        description="Review result; approved cannot coexist with high or critical findings.",
    ),
    "TaskCompletionResult": _object(
        {
            "status": {"type": "string", "enum": ["completed", "failed"]},
            "summary": _string("Concise implemented outcome."),
            "reasoning": _string("Repository-grounded implementation reasoning."),
            "modified_files": _string_list("Exact paths changed by controlled tools."),
            "tests_passed": {"type": "boolean"},
            "citations": _string_list("Repository path and line citations.", minimum=1),
            "unresolved_findings": _string_list("Known non-blocking limitations."),
            "pr_summary": {"type": "string", "description": "Optional pull-request summary."},
        },
        [
            "status",
            "summary",
            "reasoning",
            "modified_files",
            "tests_passed",
            "citations",
            "unresolved_findings",
        ],
        description="Completion claim for a repository-changing coding task.",
    ),
    "AnalysisCompletionResult": _object(
        {
            "status": {"type": "string", "enum": ["completed", "failed"]},
            "summary": _string("Concise answer to the read-only request."),
            "reasoning": _string("Reasoning grounded only in retrieved repository evidence."),
            "citations": _string_list("Repository path and line citations.", minimum=1),
            "unresolved_findings": _string_list("Known gaps or an empty list when none."),
        },
        ["status", "summary", "reasoning", "citations", "unresolved_findings"],
        description="Completion claim for a read-only repository analysis.",
    ),
}


def decision_output_schema(decision_name: str) -> dict[str, Any]:
    """Return an isolated schema so callers cannot mutate the registry."""

    try:
        return deepcopy(_DECISION_SCHEMAS[decision_name])
    except KeyError as exc:
        raise ValueError(f"unsupported structured decision: {decision_name}") from exc
