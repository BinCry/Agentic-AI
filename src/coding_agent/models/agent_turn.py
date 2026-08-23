"""Typed one-action contract for bounded iterative agent turns."""

from __future__ import annotations

import math
import re
from dataclasses import asdict, dataclass
from typing import Any

from .validation import ModelValidationError, require_choice, require_dict, require_mapping, require_string


_IDEMPOTENCY_KEY = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}")


@dataclass(slots=True, frozen=True)
class AgentToolCall:
    idempotency_key: str
    tool_name: str
    arguments: dict[str, Any]
    rationale: str

    def __post_init__(self) -> None:
        errors: list[str] = []
        if not isinstance(self.idempotency_key, str) or not _IDEMPOTENCY_KEY.fullmatch(
            self.idempotency_key
        ):
            errors.append("idempotency_key is invalid")
        if not isinstance(self.tool_name, str) or not self.tool_name.strip():
            errors.append("tool_name must be a non-empty string")
        if not isinstance(self.rationale, str) or not self.rationale.strip():
            errors.append("rationale must be a non-empty string")
        if not _is_json_value(self.arguments):
            errors.append("arguments must contain canonical finite JSON values")
        if errors:
            raise ModelValidationError(errors)

    @classmethod
    def from_dict(cls, payload: object) -> "AgentToolCall":
        value = require_mapping(payload, "tool_call")
        _reject_unknown(value, {"idempotency_key", "tool_name", "arguments", "rationale"}, "tool_call")
        return cls(
            require_string(value, "idempotency_key"),
            require_string(value, "tool_name"),
            require_dict(value, "arguments"),
            require_string(value, "rationale"),
        )


@dataclass(slots=True, frozen=True)
class AgentStageResult:
    status: str
    reason: str
    result: dict[str, Any]

    def __post_init__(self) -> None:
        require_choice({"status": self.status}, "status", {"completed", "failed", "needs_user"})
        require_string({"reason": self.reason}, "reason")
        if not isinstance(self.result, dict) or not _is_json_value(self.result):
            raise ModelValidationError(
                ["result must contain canonical finite JSON values"]
            )

    @classmethod
    def from_dict(cls, payload: object) -> "AgentStageResult":
        value = require_mapping(payload, "stage_result")
        _reject_unknown(value, {"status", "reason", "result"}, "stage_result")
        return cls(
            require_choice(value, "status", {"completed", "failed", "needs_user"}),
            require_string(value, "reason"),
            require_dict(value, "result"),
        )


@dataclass(slots=True, frozen=True)
class AgentTurnDecision:
    tool_call: AgentToolCall | None = None
    stage_result: AgentStageResult | None = None

    def __post_init__(self) -> None:
        if (self.tool_call is None) == (self.stage_result is None):
            raise ModelValidationError(
                ["agent turn requires exactly one of tool_call or stage_result"]
            )
        if self.tool_call is not None and not isinstance(self.tool_call, AgentToolCall):
            raise ModelValidationError(["tool_call must be an AgentToolCall"])
        if self.stage_result is not None and not isinstance(
            self.stage_result, AgentStageResult
        ):
            raise ModelValidationError(["stage_result must be an AgentStageResult"])

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "AgentTurnDecision":
        value = require_mapping(payload, "agent_turn")
        _reject_unknown(value, {"tool_call", "stage_result"}, "agent_turn")
        raw_tool = value.get("tool_call")
        raw_result = value.get("stage_result")
        return cls(
            AgentToolCall.from_dict(raw_tool) if raw_tool is not None else None,
            AgentStageResult.from_dict(raw_result) if raw_result is not None else None,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool_call": asdict(self.tool_call) if self.tool_call is not None else None,
            "stage_result": asdict(self.stage_result) if self.stage_result is not None else None,
        }


def _reject_unknown(value: object, allowed: set[str], label: str) -> None:
    mapping = require_mapping(value, label)
    unknown = set(mapping) - allowed
    if unknown:
        raise ModelValidationError([f"{label} contains unknown fields: {sorted(unknown)}"])


def _is_json_value(value: object) -> bool:
    if value is None or isinstance(value, (str, bool, int)):
        return True
    if isinstance(value, float):
        return math.isfinite(value)
    if isinstance(value, list):
        return all(_is_json_value(item) for item in value)
    if isinstance(value, dict):
        return all(
            isinstance(key, str)
            and bool(key)
            and _is_json_value(item)
            for key, item in value.items()
        )
    return False
