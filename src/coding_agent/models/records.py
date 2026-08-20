"""Reusable records embedded in coding task state."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .validation import (
    ModelValidationError,
    optional_string,
    require_boolean,
    require_dict,
    require_integer,
    require_mapping,
    require_number,
    require_string,
    require_string_list,
)


@dataclass(slots=True)
class RepositoryEvidence:
    chunk_id: str
    path: str
    start_line: int
    end_line: int
    content: str
    score: float
    retrieval_method: str
    file_digest: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RepositoryEvidence":
        payload = require_mapping(data, "evidence")
        start_line = require_integer(payload, "start_line", minimum=1)
        end_line = require_integer(payload, "end_line", minimum=1)
        if end_line < start_line:
            raise ModelValidationError(["end_line must not be before start_line"])
        return cls(
            chunk_id=require_string(payload, "chunk_id"),
            path=require_string(payload, "path"),
            start_line=start_line,
            end_line=end_line,
            content=require_string(payload, "content", allow_empty=True),
            score=require_number(payload, "score"),
            retrieval_method=require_string(payload, "retrieval_method"),
            file_digest=optional_string(payload, "file_digest"),
        )


@dataclass(slots=True)
class ActiveSkill:
    name: str
    path: str
    content_digest: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ActiveSkill":
        payload = require_mapping(data, "active_skill")
        digest = require_string(payload, "content_digest")
        if len(digest) != 64 or any(character not in "0123456789abcdefABCDEF" for character in digest):
            raise ModelValidationError(["content_digest must be a SHA-256 hex digest"])
        return cls(
            name=require_string(payload, "name"),
            path=require_string(payload, "path"),
            content_digest=digest.lower(),
        )


@dataclass(slots=True)
class PatchRecord:
    path: str
    patch: str
    applied: bool
    created_at: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PatchRecord":
        payload = require_mapping(data, "patch")
        return cls(
            path=require_string(payload, "path"),
            patch=require_string(payload, "patch", allow_empty=True),
            applied=require_boolean(payload, "applied"),
            created_at=require_string(payload, "created_at"),
        )


@dataclass(slots=True)
class TestExecution:
    command: list[str]
    target: str
    exit_code: int
    passed_count: int
    failed_count: int
    duration_ms: int
    stdout_summary: str
    stderr_summary: str
    timed_out: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TestExecution":
        payload = require_mapping(data, "test_execution")
        command = require_string_list(payload, "command", allow_empty=False)
        return cls(
            command=command,
            target=require_string(payload, "target"),
            exit_code=require_integer(payload, "exit_code"),
            passed_count=require_integer(payload, "passed_count", minimum=0),
            failed_count=require_integer(payload, "failed_count", minimum=0),
            duration_ms=require_integer(payload, "duration_ms", minimum=0),
            stdout_summary=require_string(payload, "stdout_summary", allow_empty=True),
            stderr_summary=require_string(payload, "stderr_summary", allow_empty=True),
            timed_out=require_boolean(payload, "timed_out"),
        )


@dataclass(slots=True)
class ErrorRecord:
    code: str
    message: str
    workflow_state: str
    created_at: str
    recoverable: bool = True

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ErrorRecord":
        payload = require_mapping(data, "error")
        return cls(
            code=require_string(payload, "code"),
            message=require_string(payload, "message"),
            workflow_state=require_string(payload, "workflow_state"),
            created_at=require_string(payload, "created_at"),
            recoverable=require_boolean(payload, "recoverable"),
        )


@dataclass(slots=True)
class CheckpointRecord:
    checkpoint_id: str
    workflow_state: str
    state_path: str
    created_at: str
    reason: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CheckpointRecord":
        payload = require_mapping(data, "checkpoint")
        return cls(
            checkpoint_id=require_string(payload, "checkpoint_id"),
            workflow_state=require_string(payload, "workflow_state"),
            state_path=require_string(payload, "state_path"),
            created_at=require_string(payload, "created_at"),
            reason=require_string(payload, "reason"),
        )


@dataclass(slots=True)
class ToolTraceRecord:
    event_id: str
    timestamp: str
    workflow_state: str
    skill: str | None
    tool: str
    success: bool
    latency_ms: int
    input_metadata: dict[str, Any] = field(default_factory=dict)
    result_metadata: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ToolTraceRecord":
        payload = require_mapping(data, "tool_trace")
        return cls(
            event_id=require_string(payload, "event_id"),
            timestamp=require_string(payload, "timestamp"),
            workflow_state=require_string(payload, "workflow_state"),
            skill=optional_string(payload, "skill"),
            tool=require_string(payload, "tool"),
            success=require_boolean(payload, "success"),
            latency_ms=require_integer(payload, "latency_ms", minimum=0),
            input_metadata=require_dict(payload, "input_metadata"),
            result_metadata=require_dict(payload, "result_metadata"),
            error=optional_string(payload, "error"),
        )


def records_to_dict(records: list[Any]) -> list[dict[str, Any]]:
    return [asdict(record) for record in records]
