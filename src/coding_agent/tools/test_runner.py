"""Named, allowlisted test profiles with bounded execution."""

from __future__ import annotations

import re
import sys
import time
from pathlib import Path

from ..models.records import TestExecution
from ..storage.workspace import WorkspacePaths
from .process import run_bounded, safe_environment


class TestRunnerError(ValueError):
    """Raised when a test profile is not approved or cannot run."""


class TestProfileNotFoundError(TestRunnerError):
    """Raised for a test command outside the named allowlist."""


class AllowlistedTestRunner:
    PROFILES = {
        "unit": ("-B", "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py", "-v"),
        "fixture": (
            "-B",
            "-m",
            "unittest",
            "discover",
            "-s",
            "tests/fixtures/sample_repo",
            "-p",
            "test_*.py",
            "-v",
        ),
    }

    def __init__(self, paths: WorkspacePaths, *, maximum_output_bytes: int = 64_000) -> None:
        self.paths = paths
        self.maximum_output_bytes = maximum_output_bytes

    def run(self, profile: str, *, timeout_seconds: float = 60.0) -> TestExecution:
        try:
            suffix = self.PROFILES[profile]
        except KeyError as exc:
            raise TestProfileNotFoundError(f"test profile is not allowlisted: {profile}") from exc
        started = time.perf_counter()
        result = run_bounded(
            [sys.executable, *suffix],
            cwd=self.paths.workspace_root,
            timeout_seconds=timeout_seconds,
            maximum_output_bytes=self.maximum_output_bytes,
            environment=safe_environment(self.paths.workspace_root, self.paths.runtime_root),
        )
        duration_ms = int((time.perf_counter() - started) * 1000)
        report = result.stdout + "\n" + result.stderr
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
            duration_ms=duration_ms,
            stdout_summary=result.stdout,
            stderr_summary=result.stderr,
            timed_out=result.timed_out,
        )

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
        return {"frameworks": sorted(frameworks), "test_roots": sorted(roots)}


def _first_int(pattern: str, text: str) -> int | None:
    match = re.search(pattern, text, flags=re.IGNORECASE)
    return int(match.group(1)) if match else None
