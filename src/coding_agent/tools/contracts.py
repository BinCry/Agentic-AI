"""Typed contracts at the boundary of controlled Phase 2 tools."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any


class ToolCategory(StrEnum):
    READ = "read"
    MUTATION = "mutation"
    TEST = "test"
    GIT = "git"


class ToolRisk(StrEnum):
    READ = "read"
    WORKSPACE_WRITE = "workspace-write"
    DESTRUCTIVE = "destructive"
    PROCESS = "process"
    NETWORK = "network"
    REMOTE_WRITE = "remote-write"


@dataclass(slots=True, frozen=True)
class ToolSpec:
    name: str
    category: ToolCategory
    read_only: bool
    requires_approval: bool
    allowed_states: frozenset[str]
    timeout_seconds: float = 30.0
    maximum_output_bytes: int = 64_000
    risks: frozenset[ToolRisk] = frozenset({ToolRisk.READ})

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["category"] = self.category.value
        payload["allowed_states"] = sorted(self.allowed_states)
        payload["risks"] = sorted(item.value for item in self.risks)
        return payload


@dataclass(slots=True, frozen=True)
class ToolRequest:
    request_id: str
    task_id: str
    tool_name: str
    arguments: dict[str, Any] = field(default_factory=dict)
    workflow_state: str = ""

    def arguments_hash(self) -> str:
        encoded = json.dumps(
            self.arguments,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


@dataclass(slots=True, frozen=True)
class PendingToolCall:
    request_id: str
    task_id: str
    tool_name: str
    arguments_hash: str
    workflow_state: str
    reason: str
    created_at: str
    arguments: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "PendingToolCall":
        required = ("request_id", "task_id", "tool_name", "arguments_hash", "workflow_state", "reason", "created_at")
        if any(not isinstance(payload.get(key), str) or not payload[key] for key in required):
            raise ValueError("pending tool call contains invalid fields")
        arguments = payload.get("arguments", {})
        if not isinstance(arguments, dict):
            raise ValueError("pending tool call arguments must be an object")
        pending = cls(**{key: payload[key] for key in required}, arguments=dict(arguments))
        if arguments:
            request = ToolRequest(
                pending.request_id,
                pending.task_id,
                pending.tool_name,
                pending.arguments,
                pending.workflow_state,
            )
            if request.arguments_hash() != pending.arguments_hash:
                raise ValueError("pending tool call arguments do not match their hash")
        return pending


@dataclass(slots=True, frozen=True)
class ToolResult:
    tool_name: str
    success: bool
    output: Any = None
    error_code: str | None = None
    error_message: str | None = None
    timed_out: bool = False
    truncated: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def failure(
        cls,
        tool_name: str,
        error_code: str,
        error_message: str,
        *,
        timed_out: bool = False,
    ) -> "ToolResult":
        return cls(
            tool_name=tool_name,
            success=False,
            error_code=error_code,
            error_message=error_message,
            timed_out=timed_out,
        )
