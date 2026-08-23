"""Immutable, JSON-safe project discovery value objects."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


def _text(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{key} must be a non-empty string")
    return value


def _strings(payload: dict[str, Any], key: str) -> tuple[str, ...]:
    value = payload.get(key, [])
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
        raise ValueError(f"{key} must be a list of non-empty strings")
    return tuple(value)


@dataclass(slots=True, frozen=True)
class InstructionBlock:
    path: str
    scope: str
    sha256: str
    content: str
    truncated: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "scope": self.scope,
            "sha256": self.sha256,
            "content": self.content,
            "truncated": self.truncated,
        }

    @classmethod
    def from_dict(cls, payload: object) -> "InstructionBlock":
        if not isinstance(payload, dict):
            raise ValueError("instruction block must be an object")
        truncated = payload.get("truncated", False)
        content = payload.get("content")
        if not isinstance(content, str) or not isinstance(truncated, bool):
            raise ValueError("instruction content/truncated values are invalid")
        digest = _text(payload, "sha256")
        if len(digest) != 64:
            raise ValueError("instruction sha256 must contain 64 characters")
        return cls(_text(payload, "path"), _text(payload, "scope"), digest, content, truncated)


@dataclass(slots=True, frozen=True)
class ManifestRecord:
    path: str
    ecosystem: str
    kind: str
    sha256: str

    def to_dict(self) -> dict[str, str]:
        return {
            "path": self.path,
            "ecosystem": self.ecosystem,
            "kind": self.kind,
            "sha256": self.sha256,
        }

    @classmethod
    def from_dict(cls, payload: object) -> "ManifestRecord":
        if not isinstance(payload, dict):
            raise ValueError("manifest must be an object")
        digest = _text(payload, "sha256")
        if len(digest) != 64:
            raise ValueError("manifest sha256 must contain 64 characters")
        return cls(
            _text(payload, "path"),
            _text(payload, "ecosystem"),
            _text(payload, "kind"),
            digest,
        )


@dataclass(slots=True, frozen=True)
class CommandCandidate:
    purpose: str
    argv: tuple[str, ...]
    source: str

    def to_dict(self) -> dict[str, Any]:
        return {"purpose": self.purpose, "argv": list(self.argv), "source": self.source}

    @classmethod
    def from_dict(cls, payload: object) -> "CommandCandidate":
        if not isinstance(payload, dict):
            raise ValueError("command candidate must be an object")
        argv = _strings(payload, "argv")
        if not argv:
            raise ValueError("command argv must not be empty")
        return cls(_text(payload, "purpose"), argv, _text(payload, "source"))


@dataclass(slots=True, frozen=True)
class ProjectProfile:
    schema_version: int
    workspace_name: str
    ecosystems: tuple[str, ...]
    package_managers: tuple[str, ...]
    manifests: tuple[ManifestRecord, ...]
    commands: tuple[CommandCandidate, ...]
    instructions: tuple[InstructionBlock, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "workspace_name": self.workspace_name,
            "ecosystems": list(self.ecosystems),
            "package_managers": list(self.package_managers),
            "manifests": [item.to_dict() for item in self.manifests],
            "commands": [item.to_dict() for item in self.commands],
            "instructions": [item.to_dict() for item in self.instructions],
        }

    @classmethod
    def from_dict(cls, payload: object) -> "ProjectProfile":
        if not isinstance(payload, dict) or payload.get("schema_version") != 1:
            raise ValueError("project profile requires schema_version 1")
        manifests = payload.get("manifests", [])
        commands = payload.get("commands", [])
        instructions = payload.get("instructions", [])
        if not all(isinstance(value, list) for value in (manifests, commands, instructions)):
            raise ValueError("project profile record groups must be lists")
        return cls(
            1,
            _text(payload, "workspace_name"),
            _strings(payload, "ecosystems"),
            _strings(payload, "package_managers"),
            tuple(ManifestRecord.from_dict(item) for item in manifests),
            tuple(CommandCandidate.from_dict(item) for item in commands),
            tuple(InstructionBlock.from_dict(item) for item in instructions),
        )
