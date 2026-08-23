"""Typed command values passed across the execution trust boundary."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Mapping


@dataclass(slots=True, frozen=True)
class CommandRequest:
    executable: str
    arguments: tuple[str, ...] = ()
    cwd: str = "."
    environment: Mapping[str, str] = field(default_factory=dict)
    timeout_seconds: float = 60.0
    maximum_output_bytes: int = 64_000


@dataclass(slots=True, frozen=True)
class PreparedCommand:
    argv: tuple[str, ...]
    cwd: Path
    environment: tuple[tuple[str, str], ...]
    timeout_seconds: float
    maximum_output_bytes: int


@dataclass(slots=True, frozen=True)
class CommandResult:
    command: tuple[str, ...]
    exit_code: int
    timed_out: bool
    stdout_truncated: bool
    stderr_truncated: bool
    duration_ms: int
    stdout_sha256: str
    stderr_sha256: str
    stdout_excerpt: str
    stderr_excerpt: str

    @property
    def truncated(self) -> bool:
        return self.stdout_truncated or self.stderr_truncated

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["command"] = list(self.command)
        payload["truncated"] = self.truncated
        return payload
