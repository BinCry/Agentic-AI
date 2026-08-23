"""Deterministic Python/Node verification registry and execution facade."""

from __future__ import annotations

from ..policy.models import WorkspaceTrust
from ..storage.workspace import WorkspacePaths
from ..tools.command_models import CommandResult
from ..tools.command_service import CommandService
from .models import VerificationProfile
from .node_adapter import discover_node_profiles
from .python_adapter import discover_python_profiles


class VerificationProfileNotFoundError(ValueError):
    """Raised with deterministic alternatives for an unknown profile."""

    def __init__(self, name: str, alternatives: tuple[str, ...]) -> None:
        self.name = name
        self.alternatives = alternatives
        available = ", ".join(alternatives) or "none"
        super().__init__(f"verification profile not found: {name}; available: {available}")


class VerificationRegistry:
    def __init__(
        self,
        paths: WorkspacePaths,
        *,
        command_service: CommandService | None = None,
    ) -> None:
        self.paths = paths
        self.commands = command_service or CommandService(paths)

    def list(self) -> tuple[VerificationProfile, ...]:
        profiles = [
            *discover_python_profiles(self.paths),
            *discover_node_profiles(self.paths),
        ]
        return tuple(sorted(profiles, key=lambda item: item.name))

    def detect(self, name: str) -> VerificationProfile:
        if not isinstance(name, str) or not name:
            raise VerificationProfileNotFoundError(str(name), self._alternatives())
        profiles = {item.name: item for item in self.list()}
        if name == "unit":
            for candidate in ("python.test", "node.test"):
                if candidate in profiles:
                    return profiles[candidate]
        try:
            return profiles[name]
        except KeyError as exc:
            raise VerificationProfileNotFoundError(name, tuple(profiles)) from exc

    def run(self, name: str, *, trust: WorkspaceTrust) -> CommandResult:
        profile = self.detect(name)
        prepared = self.commands.prepare(profile.command)
        return self.commands.execute(prepared, trust=trust)

    def _alternatives(self) -> tuple[str, ...]:
        return tuple(item.name for item in self.list())
