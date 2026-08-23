"""Immutable verification profile discovered from repository evidence."""

from __future__ import annotations

from dataclasses import dataclass

from ..tools.command_models import CommandRequest


@dataclass(slots=True, frozen=True)
class VerificationProfile:
    name: str
    ecosystem: str
    kind: str
    command: CommandRequest
    source: str

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "ecosystem": self.ecosystem,
            "kind": self.kind,
            "command": {
                "executable": self.command.executable,
                "arguments": list(self.command.arguments),
                "cwd": self.command.cwd,
                "timeout_seconds": self.command.timeout_seconds,
                "maximum_output_bytes": self.command.maximum_output_bytes,
            },
            "source": self.source,
        }
