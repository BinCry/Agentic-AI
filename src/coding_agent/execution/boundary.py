"""Explicit isolation boundary for bounded local process execution."""

from __future__ import annotations

import hashlib
from typing import Protocol

from ..observability.trace import redact_text
from ..policy.models import WorkspaceTrust
from ..storage.workspace import WorkspacePaths
from ..tools.command_models import CommandResult, PreparedCommand
from ..tools.process import run_bounded, safe_environment


class ExecutionBoundaryError(PermissionError):
    """Raised when a command has no configured isolation boundary."""


class ExecutionBoundary(Protocol):
    def execute(self, request: PreparedCommand, trust: WorkspaceTrust) -> CommandResult: ...


class LocalTrustedBoundary:
    """Run locally only when the caller explicitly marks the workspace trusted."""

    def __init__(self, paths: WorkspacePaths) -> None:
        self.paths = paths

    def execute(self, request: PreparedCommand, trust: WorkspaceTrust) -> CommandResult:
        if trust is not WorkspaceTrust.TRUSTED:
            raise ExecutionBoundaryError(
                "local process execution requires an explicitly trusted workspace"
            )
        environment = safe_environment(self.paths.workspace_root, self.paths.runtime_root)
        environment.update(dict(request.environment))
        result = run_bounded(
            list(request.argv),
            cwd=request.cwd,
            timeout_seconds=request.timeout_seconds,
            maximum_output_bytes=request.maximum_output_bytes,
            environment=environment,
        )
        stdout = redact_text(result.stdout)
        stderr = redact_text(result.stderr)
        return CommandResult(
            command=result.command,
            exit_code=result.exit_code,
            timed_out=result.timed_out,
            stdout_truncated=result.stdout_truncated,
            stderr_truncated=result.stderr_truncated,
            duration_ms=result.duration_ms,
            stdout_sha256=hashlib.sha256(result.stdout.encode("utf-8")).hexdigest(),
            stderr_sha256=hashlib.sha256(result.stderr.encode("utf-8")).hexdigest(),
            stdout_excerpt=stdout,
            stderr_excerpt=stderr,
        )
