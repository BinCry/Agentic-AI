"""Named, allowlisted test profiles with bounded execution."""

from __future__ import annotations

import re
from dataclasses import replace

from ..models.records import TestExecution
from ..policy.models import WorkspaceTrust
from ..storage.workspace import WorkspacePaths
from ..verification import VerificationProfileNotFoundError, VerificationRegistry


class TestRunnerError(ValueError):
    """Raised when a test profile is not approved or cannot run."""


class TestProfileNotFoundError(TestRunnerError):
    """Raised for a test command outside the named allowlist."""


class AllowlistedTestRunner:
    PROFILES = ("fixture", "unit", "python.test", "node.test")

    def __init__(
        self,
        paths: WorkspacePaths,
        *,
        maximum_output_bytes: int = 64_000,
        workspace_trust: WorkspaceTrust = WorkspaceTrust.TRUSTED,
    ) -> None:
        self.paths = paths
        self.maximum_output_bytes = maximum_output_bytes
        self.workspace_trust = workspace_trust
        self.registry = VerificationRegistry(paths)

    def run(self, profile: str, *, timeout_seconds: float = 60.0) -> TestExecution:
        try:
            detected = self.registry.detect(profile)
            command = detected.command
            command = replace(
                command,
                timeout_seconds=timeout_seconds,
                maximum_output_bytes=self.maximum_output_bytes,
            )
            result = self.registry.commands.execute(
                self.registry.commands.prepare(command),
                trust=self.workspace_trust,
            )
        except KeyError as exc:
            raise TestProfileNotFoundError(f"test profile is not allowlisted: {profile}") from exc
        except VerificationProfileNotFoundError as exc:
            raise TestProfileNotFoundError(str(exc)) from exc
        report = result.stdout_excerpt + "\n" + result.stderr_excerpt
        ran = _first_int(r"Ran\s+(\d+)\s+tests?", report) or 0
        failures = _first_int(r"failures?=(\d+)", report) or 0
        errors = _first_int(r"errors?=(\d+)", report) or 0
        failed_count = failures + errors
        if result.exit_code != 0 and failed_count == 0 and ran:
            failed_count = 1
        return TestExecution(
            command=list(result.command),
            target=profile,
            exit_code=result.exit_code,
            passed_count=max(ran - failed_count, 0),
            failed_count=failed_count,
            duration_ms=result.duration_ms,
            stdout_summary=result.stdout_excerpt,
            stderr_summary=result.stderr_excerpt,
            timed_out=result.timed_out,
            output_truncated=result.truncated,
        )

    def select_profiles(self, configured: list[str]) -> list[str]:
        try:
            return list(self.registry.select(configured))
        except VerificationProfileNotFoundError as exc:
            raise TestProfileNotFoundError(str(exc)) from exc

    def detect_framework(self) -> dict[str, object]:
        """Detect only known Python test conventions using bounded source reads."""
        frameworks: set[str] = set()
        roots: set[str] = set()
        files = sorted(self.paths.workspace_root.rglob("*.py"))
        for path in files[:2_000]:
            if path.is_relative_to(self.paths.runtime_root) or any(
                part in {".git", "__pycache__", ".venv", "node_modules"}
                for part in path.parts
            ):
                continue
            try:
                source = path.read_text(encoding="utf-8")[:100_000]
            except (OSError, UnicodeDecodeError):
                continue
            relative = str(path.relative_to(self.paths.workspace_root)).replace("\\", "/")
            if "unittest" in source or "TestCase" in source:
                frameworks.add("unittest")
            if "pytest" in source or "import pytest" in source:
                frameworks.add("pytest")
            if relative.startswith("tests/"):
                roots.add("tests")
        profiles = self.registry.list()
        if any(item.ecosystem == "node" for item in profiles):
            frameworks.add("node:test")
            roots.add(".")
        return {
            "frameworks": sorted(frameworks),
            "test_roots": sorted(roots),
            "profiles": [item.name for item in profiles],
        }


def _first_int(pattern: str, text: str) -> int | None:
    match = re.search(pattern, text, flags=re.IGNORECASE)
    return int(match.group(1)) if match else None
