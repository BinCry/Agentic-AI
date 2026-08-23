"""Pure command normalization followed by an explicit execution boundary."""

from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

from ..execution.boundary import ExecutionBoundary, LocalTrustedBoundary
from ..observability.trace import HIGH_CONFIDENCE_SECRET_RE
from ..policy.models import WorkspaceTrust
from ..storage.workspace import WorkspacePaths, WorkspacePolicyError
from .command_models import CommandRequest, CommandResult, PreparedCommand


class CommandValidationError(ValueError):
    """Raised before process creation when a command is outside the safe grammar."""


_SAFE_ENVIRONMENT_NAMES = frozenset({"CI", "FORCE_COLOR", "LANG", "LC_ALL", "NO_COLOR"})
_SENSITIVE_NAME_PARTS = ("AUTH", "CREDENTIAL", "KEY", "PASSWORD", "SECRET", "TOKEN")
_SHELL_META = re.compile(r"[&|<>`$\r\n\x00]")
_DIRECT_EXECUTABLES = frozenset({"node"})
_UNITTEST_PATTERN = re.compile(r"[A-Za-z0-9_*?.-]{1,128}")


class CommandService:
    MINIMUM_TIMEOUT_SECONDS = 0.05
    MAXIMUM_TIMEOUT_SECONDS = 600.0
    MAXIMUM_OUTPUT_BYTES = 1_048_576

    def __init__(
        self,
        paths: WorkspacePaths,
        *,
        boundary: ExecutionBoundary | None = None,
    ) -> None:
        self.paths = paths
        self.boundary = boundary or LocalTrustedBoundary(paths)

    def prepare(self, request: CommandRequest) -> PreparedCommand:
        executable = self._resolve_executable(request.executable)
        cwd = self._resolve_cwd(request.cwd)
        arguments = self._validate_arguments(
            request.executable, request.arguments, cwd
        )
        environment = self._validate_environment(request.environment)
        timeout = request.timeout_seconds
        if (
            isinstance(timeout, bool)
            or not isinstance(timeout, (int, float))
            or not self.MINIMUM_TIMEOUT_SECONDS <= float(timeout) <= self.MAXIMUM_TIMEOUT_SECONDS
        ):
            raise CommandValidationError("timeout_seconds is outside the supported range")
        maximum_output = request.maximum_output_bytes
        if (
            isinstance(maximum_output, bool)
            or not isinstance(maximum_output, int)
            or not 1 <= maximum_output <= self.MAXIMUM_OUTPUT_BYTES
        ):
            raise CommandValidationError("maximum_output_bytes is outside the supported range")
        return PreparedCommand(
            (executable, *arguments),
            cwd,
            environment,
            float(timeout),
            maximum_output,
        )

    def execute(
        self,
        request: PreparedCommand,
        *,
        trust: WorkspaceTrust,
    ) -> CommandResult:
        if not isinstance(trust, WorkspaceTrust):
            raise CommandValidationError("workspace trust must be typed")
        return self.boundary.execute(request, trust)

    def _resolve_executable(self, value: str) -> str:
        if not isinstance(value, str) or not value or _SHELL_META.search(value):
            raise CommandValidationError("executable contains unsupported shell syntax")
        if Path(value).name != value:
            raise CommandValidationError("executable must be a registered command name")
        normalized = value.casefold()
        if normalized in {"python", "python3", "py"}:
            return sys.executable
        if normalized not in _DIRECT_EXECUTABLES:
            raise CommandValidationError(f"executable is not registered: {value}")
        resolved = shutil.which(normalized)
        if not resolved:
            raise CommandValidationError(f"registered executable is unavailable: {value}")
        return str(Path(resolved).resolve())

    def _validate_arguments(
        self,
        executable: str,
        values: tuple[str, ...],
        cwd: Path,
    ) -> tuple[str, ...]:
        if not isinstance(values, tuple) or any(
            not isinstance(item, str) or not item or "\x00" in item or "\r" in item or "\n" in item
            for item in values
        ):
            raise CommandValidationError("arguments must be non-empty, NUL-free argv strings")
        normalized = executable.casefold()
        if normalized in {"python", "python3", "py"}:
            offset = 1 if values[:1] == ("-B",) else 0
            if values[offset : offset + 2] != ("-m", "unittest"):
                raise CommandValidationError(
                    "Python execution is limited to the registered unittest module"
                )
            self._validate_unittest_arguments(values[offset + 2 :], cwd)
            return values
        if values != ("--test",):
            raise CommandValidationError("Node execution is limited to the built-in test runner")
        return values

    def _validate_unittest_arguments(self, values: tuple[str, ...], cwd: Path) -> None:
        if not values:
            return
        if values[0] != "discover":
            raise CommandValidationError("unittest is limited to discovery mode")
        index = 1
        while index < len(values):
            flag = values[index]
            if flag in {"-v", "--verbose"}:
                index += 1
                continue
            if flag in {"-s", "--start-directory", "-t", "--top-level-directory"}:
                if index + 1 >= len(values):
                    raise CommandValidationError(f"missing path value for unittest flag: {flag}")
                self._validate_test_directory(cwd, values[index + 1])
                index += 2
                continue
            if flag in {"-p", "--pattern"}:
                if (
                    index + 1 >= len(values)
                    or not _UNITTEST_PATTERN.fullmatch(values[index + 1])
                ):
                    raise CommandValidationError("unittest pattern is invalid")
                index += 2
                continue
            raise CommandValidationError(f"unsupported unittest argument: {flag}")

    def _validate_test_directory(self, cwd: Path, value: str) -> None:
        candidate = Path(value)
        if candidate.is_absolute():
            raise CommandValidationError("unittest paths must be workspace-relative")
        try:
            resolved = self.paths.resolve_workspace_path(
                (cwd / candidate).resolve(), must_exist=True
            )
        except WorkspacePolicyError as exc:
            raise CommandValidationError(str(exc)) from exc
        if not resolved.is_dir():
            raise CommandValidationError("unittest path must resolve to a directory")

    def _resolve_cwd(self, value: str) -> Path:
        if not isinstance(value, str) or not value:
            raise CommandValidationError("cwd must be a non-empty workspace-relative path")
        try:
            resolved = self.paths.resolve_workspace_path(value, must_exist=True)
        except WorkspacePolicyError as exc:
            raise CommandValidationError(str(exc)) from exc
        if not resolved.is_dir():
            raise CommandValidationError("cwd must resolve to a directory")
        return resolved

    @staticmethod
    def _validate_environment(values: object) -> tuple[tuple[str, str], ...]:
        if not isinstance(values, dict):
            raise CommandValidationError("environment must be an object")
        output: list[tuple[str, str]] = []
        for name, value in values.items():
            if not isinstance(name, str) or not isinstance(value, str):
                raise CommandValidationError("environment names and values must be strings")
            upper = name.upper()
            if any(part in upper for part in _SENSITIVE_NAME_PARTS):
                raise CommandValidationError(f"sensitive environment variable is forbidden: {name}")
            if upper not in _SAFE_ENVIRONMENT_NAMES:
                raise CommandValidationError(f"environment variable is not allowlisted: {name}")
            if "\x00" in value or "\r" in value or "\n" in value:
                raise CommandValidationError(f"environment value is invalid: {name}")
            if HIGH_CONFIDENCE_SECRET_RE.search(value):
                raise CommandValidationError(
                    f"environment value resembles a credential: {name}"
                )
            output.append((upper, value))
        return tuple(sorted(output))
