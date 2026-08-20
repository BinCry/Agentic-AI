"""Read-only Git status and diff adapter with no arbitrary arguments."""

from __future__ import annotations

import time

from ..storage.workspace import WorkspacePaths, WorkspacePolicyError
from .process import run_bounded, safe_environment


class GitToolError(ValueError):
    """Raised when a Git read-only operation is invalid."""


class ReadOnlyGitService:
    def __init__(self, paths: WorkspacePaths, *, maximum_output_bytes: int = 64_000) -> None:
        self.paths = paths
        self.maximum_output_bytes = maximum_output_bytes

    def status(self) -> str:
        return self._run(["status", "--short", "--branch"])

    def diff(self, paths: list[str] | None = None) -> str:
        command = ["diff", "--"]
        command.extend(self._relative_path(item) for item in (paths or []))
        return self._run(command)

    def changed_files(self) -> list[str]:
        output = self._run(["diff", "--name-only", "HEAD", "--"])
        return [line.replace("\\", "/") for line in output.splitlines() if line.strip()]

    def _run(self, git_arguments: list[str]) -> str:
        started = time.perf_counter()
        result = run_bounded(
            ["git", "-C", str(self.paths.workspace_root), *git_arguments],
            cwd=self.paths.workspace_root,
            timeout_seconds=30.0,
            maximum_output_bytes=self.maximum_output_bytes,
            environment=safe_environment(self.paths.workspace_root, self.paths.runtime_root),
        )
        if result.timed_out:
            raise GitToolError("git operation timed out")
        if result.exit_code != 0:
            raise GitToolError(result.stderr[:2_000] or "git operation failed")
        return result.stdout

    def _relative_path(self, value: str) -> str:
        try:
            resolved = self.paths.resolve_workspace_path(value)
        except WorkspacePolicyError as exc:
            raise GitToolError(str(exc)) from exc
        return str(resolved.relative_to(self.paths.workspace_root))
