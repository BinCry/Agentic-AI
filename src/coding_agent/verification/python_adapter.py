"""Conservative Python verification profile discovery."""

from __future__ import annotations

from pathlib import Path

from ..storage.workspace import WorkspacePaths, WorkspacePolicyError
from ..tools.command_models import CommandRequest
from .models import VerificationProfile


def discover_python_profiles(paths: WorkspacePaths) -> tuple[VerificationProfile, ...]:
    profiles: list[VerificationProfile] = []
    tests = paths.workspace_root / "tests"
    if tests.is_dir() and _contains_test_module(paths, tests):
        profiles.append(
            VerificationProfile(
                "python.test",
                "python",
                "test",
                CommandRequest(
                    "python",
                    ("-B", "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py", "-v"),
                ),
                "observed tests/test*.py",
            )
        )
    fixture = paths.workspace_root / "tests" / "fixtures" / "sample_repo"
    if fixture.is_dir() and _contains_test_module(paths, fixture):
        profiles.append(
            VerificationProfile(
                "fixture",
                "python",
                "test",
                CommandRequest(
                    "python",
                    (
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
                ),
                "bundled compatibility fixture",
            )
        )
    return tuple(profiles)


def _contains_test_module(paths: WorkspacePaths, root: Path) -> bool:
    for index, candidate in enumerate(root.rglob("test*.py")):
        if index >= 2_000:
            return False
        try:
            resolved = paths.resolve_workspace_path(candidate, must_exist=True)
        except WorkspacePolicyError:
            continue
        if resolved.is_file():
            return True
    return False
