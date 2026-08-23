"""Workspace containment and writable-path policy."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


class WorkspacePolicyError(ValueError):
    """Raised when a path escapes the workspace or targets a forbidden drive."""


@dataclass(slots=True, frozen=True)
class WorkspacePaths:
    workspace_root: Path
    runtime_root: Path
    forbidden_drives: frozenset[str] = frozenset({"C:"})

    @classmethod
    def create(
        cls,
        workspace_root: str | Path,
        runtime_root: str | Path = ".coding-agent",
        *,
        forbidden_drives: frozenset[str] = frozenset({"C:"}),
    ) -> "WorkspacePaths":
        workspace = Path(workspace_root).resolve()
        runtime_candidate = Path(runtime_root)
        runtime = (
            runtime_candidate.resolve()
            if runtime_candidate.is_absolute()
            else (workspace / runtime_candidate).resolve()
        )
        instance = cls(workspace, runtime, frozenset(item.upper() for item in forbidden_drives))
        instance._validate_path(workspace, "workspace_root")
        instance._validate_path(runtime, "runtime_root")
        if not runtime.is_relative_to(workspace):
            raise WorkspacePolicyError("runtime_root must remain inside workspace_root")
        return instance

    def ensure(self) -> "WorkspacePaths":
        if not self.workspace_root.is_dir():
            raise WorkspacePolicyError(f"workspace does not exist: {self.workspace_root}")
        self.runtime_root.mkdir(parents=True, exist_ok=True)
        return self

    def resolve_workspace_path(self, value: str | Path, *, must_exist: bool = False) -> Path:
        candidate = Path(value)
        resolved = candidate.resolve() if candidate.is_absolute() else (self.workspace_root / candidate).resolve()
        self._validate_path(resolved, "path")
        if not resolved.is_relative_to(self.workspace_root):
            raise WorkspacePolicyError(f"path escapes workspace: {value}")
        if must_exist and not resolved.exists():
            raise WorkspacePolicyError(f"path does not exist: {value}")
        return resolved

    def resolve_readonly_path(self, value: str | Path, *, must_exist: bool = False) -> Path:
        """Resolve an explicit read-only dependency without granting write scope."""
        candidate = Path(value)
        resolved = (
            candidate.resolve()
            if candidate.is_absolute()
            else (self.workspace_root / candidate).resolve()
        )
        self._validate_path(resolved, "read-only path")
        if must_exist and not resolved.exists():
            raise WorkspacePolicyError(f"read-only path does not exist: {value}")
        return resolved

    def resolve_runtime_path(self, value: str | Path, *, must_exist: bool = False) -> Path:
        candidate = Path(value)
        resolved = candidate.resolve() if candidate.is_absolute() else (self.runtime_root / candidate).resolve()
        self._validate_path(resolved, "runtime path")
        if not resolved.is_relative_to(self.runtime_root):
            raise WorkspacePolicyError(f"path escapes runtime root: {value}")
        if not resolved.is_relative_to(self.workspace_root):
            raise WorkspacePolicyError(f"path escapes workspace: {value}")
        if must_exist and not resolved.exists():
            raise WorkspacePolicyError(f"path does not exist: {value}")
        return resolved

    def task_path(self, task_id: str) -> Path:
        return self.resolve_runtime_path(Path("tasks") / f"{task_id}.json")

    def trace_path(self, task_id: str) -> Path:
        return self.resolve_runtime_path(Path("traces") / f"{task_id}.jsonl")

    def _validate_path(self, path: Path, label: str) -> None:
        drive = path.drive.upper()
        if drive and drive in self.forbidden_drives:
            raise WorkspacePolicyError(f"{label} uses forbidden drive {drive}")
