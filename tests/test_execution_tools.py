from __future__ import annotations

import sys
import unittest

from coding_agent.storage.workspace import WorkspacePaths
from coding_agent.tools.git_service import GitToolError, ReadOnlyGitService
from coding_agent.tools.process import run_bounded, safe_environment
from coding_agent.tools.test_runner import AllowlistedTestRunner, TestProfileNotFoundError

from tests.support import WorkspaceTestCase


class ExecutionToolTests(WorkspaceTestCase):
    def make_paths(self) -> WorkspacePaths:
        return WorkspacePaths.create(self.test_root).ensure()

    def make_git_paths(self) -> WorkspacePaths:
        paths = self.make_paths()
        result = run_bounded(
            ["git", "init", "--quiet"],
            cwd=paths.workspace_root,
            timeout_seconds=10.0,
            maximum_output_bytes=4_096,
            environment=safe_environment(paths.workspace_root, paths.runtime_root),
        )
        if result.exit_code != 0:
            self.fail(f"failed to initialize isolated Git fixture: {result.stderr}")
        commit = run_bounded(
            [
                "git",
                "-c",
                "user.name=Fixture",
                "-c",
                "user.email=fixture@example.invalid",
                "commit",
                "--allow-empty",
                "--quiet",
                "-m",
                "initialize fixture",
            ],
            cwd=paths.workspace_root,
            timeout_seconds=10.0,
            maximum_output_bytes=4_096,
            environment=safe_environment(paths.workspace_root, paths.runtime_root),
        )
        if commit.exit_code != 0:
            self.fail(f"failed to commit isolated Git fixture: {commit.stderr}")
        return paths

    def test_unknown_test_profile_is_rejected(self) -> None:
        with self.assertRaises(TestProfileNotFoundError):
            AllowlistedTestRunner(self.make_paths()).run("arbitrary-command")

    def test_detect_framework_reports_unittest_fixture(self) -> None:
        tests = self.test_root / "tests"
        tests.mkdir()
        (tests / "test_sample.py").write_text(
            "import unittest\nclass Sample(unittest.TestCase):\n    pass\n",
            encoding="utf-8",
        )
        detected = AllowlistedTestRunner(self.make_paths()).detect_framework()
        self.assertEqual(detected["frameworks"], ["unittest"])
        self.assertEqual(detected["test_roots"], ["tests"])

    def test_bounded_process_times_out_and_caps_output(self) -> None:
        paths = self.make_paths()
        result = run_bounded(
            [sys.executable, "-u", "-c", "import time; print('x' * 1000, flush=True); time.sleep(2)"],
            cwd=paths.workspace_root,
            timeout_seconds=0.1,
            maximum_output_bytes=32,
            environment=safe_environment(paths.workspace_root, paths.runtime_root),
        )
        self.assertTrue(result.timed_out)
        self.assertTrue(result.stdout_truncated)
        self.assertLessEqual(len(result.stdout.encode("utf-8")), 32)

    def test_git_status_is_read_only_and_diff_rejects_escape(self) -> None:
        paths = self.make_git_paths()
        service = ReadOnlyGitService(paths)
        self.assertIn("##", service.status())
        with self.assertRaises(GitToolError):
            service.diff(["../outside.txt"])

    def test_changed_files_is_read_only(self) -> None:
        paths = self.make_git_paths()
        changed = ReadOnlyGitService(paths).changed_files()
        self.assertIsInstance(changed, list)


if __name__ == "__main__":
    unittest.main()
