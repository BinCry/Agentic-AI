from __future__ import annotations

import sys
import unittest
from unittest.mock import patch

from coding_agent.execution import ExecutionBoundaryError, LocalTrustedBoundary
from coding_agent.policy.models import WorkspaceTrust
from coding_agent.storage.workspace import WorkspacePaths
from coding_agent.tools.command_models import CommandRequest
from coding_agent.tools.command_service import CommandService, CommandValidationError

from tests.support import WorkspaceTestCase


class CommandServiceTests(WorkspaceTestCase):
    def make_service(self) -> CommandService:
        paths = WorkspacePaths.create(self.test_root).ensure()
        return CommandService(paths, boundary=LocalTrustedBoundary(paths))

    @staticmethod
    def unittest_request(**changes: object) -> CommandRequest:
        values: dict[str, object] = {
            "executable": "python",
            "arguments": ("-B", "-m", "unittest", "discover", "-s", "tests"),
            "cwd": ".",
            "environment": {"CI": "1"},
            "timeout_seconds": 10.0,
            "maximum_output_bytes": 4_096,
        }
        values.update(changes)
        return CommandRequest(**values)  # type: ignore[arg-type]

    def test_prepare_resolves_python_and_workspace_cwd_without_side_effects(self) -> None:
        service = self.make_service()

        prepared = service.prepare(self.unittest_request())

        self.assertEqual(prepared.argv[0], sys.executable)
        self.assertEqual(prepared.cwd, self.test_root.resolve())
        self.assertEqual(prepared.environment, (("CI", "1"),))

    def test_shell_escape_install_and_interpreter_escape_hatches_are_rejected(self) -> None:
        cases = (
            self.unittest_request(executable="python&whoami"),
            self.unittest_request(executable="powershell"),
            self.unittest_request(arguments=("-c", "print('unsafe')")),
            self.unittest_request(arguments=("-m", "pip", "install", "package")),
            self.unittest_request(executable="npm", arguments=("test",)),
            self.unittest_request(executable="npm", arguments=("install",)),
            self.unittest_request(executable="npm", arguments=("exec", "tool")),
        )
        for request in cases:
            with self.subTest(request=request), self.assertRaises(CommandValidationError):
                self.make_service().prepare(request)

    def test_cwd_escape_and_secret_environment_are_rejected(self) -> None:
        cases = (
            self.unittest_request(cwd=".."),
            self.unittest_request(environment={"OPENROUTER_API_KEY": "secret"}),
            self.unittest_request(environment={"PYTHONPATH": "outside"}),
            self.unittest_request(environment={"CI": "sk-" + "a" * 32}),
        )
        for request in cases:
            with self.subTest(request=request), self.assertRaises(CommandValidationError):
                self.make_service().prepare(request)

    def test_untrusted_workspace_is_denied_before_process_creation(self) -> None:
        service = self.make_service()
        prepared = service.prepare(self.unittest_request())

        with patch("coding_agent.tools.process.subprocess.Popen") as spawn:
            with self.assertRaises(ExecutionBoundaryError):
                service.execute(prepared, trust=WorkspaceTrust.UNTRUSTED)
        spawn.assert_not_called()

    def test_trusted_execution_returns_redacted_digest_backed_excerpts(self) -> None:
        tests = self.test_root / "tests"
        tests.mkdir()
        (tests / "test_sample.py").write_text(
            "import unittest\n"
            "class Sample(unittest.TestCase):\n"
            "    def test_output(self):\n"
            "        print('token=definitely-sensitive-value')\n"
            "        print('sk-' + 'or-v1-' + 'a' * 32)\n"
            "        self.assertTrue(True)\n",
            encoding="utf-8",
        )
        service = self.make_service()

        result = service.execute(
            service.prepare(self.unittest_request()),
            trust=WorkspaceTrust.TRUSTED,
        )

        self.assertEqual(result.exit_code, 0)
        self.assertFalse(result.timed_out)
        self.assertEqual(len(result.stdout_sha256), 64)
        self.assertEqual(len(result.stderr_sha256), 64)
        self.assertNotIn("definitely-sensitive-value", result.stdout_excerpt)
        self.assertIn("[REDACTED]", result.stdout_excerpt)


if __name__ == "__main__":
    unittest.main()
