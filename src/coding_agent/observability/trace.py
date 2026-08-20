"""Append-only JSONL execution trace with secret redaction."""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from ..models.task_state import TASK_ID_PATTERN
from ..storage.workspace import WorkspacePaths

SENSITIVE_KEYS = {"api_key", "apikey", "authorization", "credential", "password", "secret", "token"}
SENSITIVE_TEXT_RE = re.compile(
    r"(?i)(bearer\s+|(?:api[_-]?key|authorization|credential|password|secret|token)"
    r"\s*[:=]\s*(?:bearer\s+)?)"
    r"([^\s,;]+)"
)


def _redact(value: Any, key: str = "") -> Any:
    if key.lower() in SENSITIVE_KEYS or any(part in key.lower() for part in SENSITIVE_KEYS):
        return "[REDACTED]"
    if isinstance(value, dict):
        return {str(item_key): _redact(item, str(item_key)) for item_key, item in value.items()}
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, tuple):
        return [_redact(item) for item in value]
    if isinstance(value, str):
        return _redact_text(value)
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return _redact_text(repr(value))


def _redact_text(value: str) -> str:
    return SENSITIVE_TEXT_RE.sub(lambda match: f"{match.group(1)}[REDACTED]", value)


@dataclass(slots=True)
class TraceEvent:
    task_id: str
    workflow_state: str
    action: str
    success: bool
    latency_ms: int
    skill: str | None = None
    tool: str | None = None
    input_metadata: dict[str, Any] = field(default_factory=dict)
    result_metadata: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    event_id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


class JsonlTraceWriter:
    def __init__(self, paths: WorkspacePaths, *, maximum_event_bytes: int = 64_000) -> None:
        self.paths = paths
        self.maximum_event_bytes = maximum_event_bytes

    def append(self, event: TraceEvent) -> None:
        if not TASK_ID_PATTERN.fullmatch(event.task_id):
            raise ValueError("task_id contains unsafe characters")
        payload = asdict(event)
        payload["input_metadata"] = _redact(event.input_metadata)
        payload["result_metadata"] = _redact(event.result_metadata)
        if payload["error"]:
            payload["error"] = _redact_text(str(payload["error"]))[:2_000]
        line = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        if len(line.encode("utf-8")) > self.maximum_event_bytes:
            raise ValueError("trace event exceeds output-size policy")
        target = self.paths.trace_path(event.task_id)
        target.parent.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(target, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o600)
        try:
            os.write(descriptor, (line + "\n").encode("utf-8"))
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
