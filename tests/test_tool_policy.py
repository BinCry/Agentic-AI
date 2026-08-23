from __future__ import annotations

import unittest

from coding_agent.policy.models import ApprovalMode, PolicyAction, WorkspaceTrust
from coding_agent.storage.workspace import WorkspacePaths
from coding_agent.tools.contracts import ToolCategory, ToolRequest, ToolSpec
from coding_agent.tools.policy import (
    ToolArgumentError,
    ToolPermissionPolicy,
    ToolStateError,
    UnknownToolError,
)

from tests.support import WorkspaceTestCase


class ToolPermissionPolicyTests(WorkspaceTestCase):
    def make_policy(self) -> ToolPermissionPolicy:
        return ToolPermissionPolicy(WorkspacePaths.create(self.test_root).ensure())

    def request(self, tool_name: str, arguments: dict[str, object] | None = None, state: str = "EDITING") -> ToolRequest:
        return ToolRequest("request-1", "task-1", tool_name, arguments or {}, state)

    def test_read_file_requires_an_existing_contained_path(self) -> None:
        target = self.test_root / "module.py"
        target.write_text("value = 1\n", encoding="utf-8")
        decision = self.make_policy().evaluate(
            self.request("repo.read_file", {"path": "module.py"})
        )
        self.assertFalse(decision.requires_approval)

    def test_traversal_and_forbidden_drive_are_rejected(self) -> None:
        policy = self.make_policy()
        with self.assertRaises(ToolArgumentError):
            policy.evaluate(self.request("repo.read_file", {"path": "../escape.py"}))
        with self.assertRaises(ToolArgumentError):
            policy.evaluate(self.request("repo.create_file", {"path": "C:/unsafe.py"}))

    def test_mutations_are_approval_gated(self) -> None:
        decision = self.make_policy().evaluate(
            self.request("repo.create_file", {"path": "new.py", "content": "x = 1\n"})
        )
        self.assertTrue(decision.requires_approval)
        self.assertEqual(decision.explanation.action, PolicyAction.ASK)
        self.assertEqual(decision.explanation.reason_code, "WRITE_APPROVAL_REQUIRED")

    def test_read_only_and_auto_edit_modes_only_reduce_or_bound_authority(self) -> None:
        paths = WorkspacePaths.create(self.test_root).ensure()
        request = self.request(
            "repo.create_file", {"path": "new.py", "content": "x = 1\n"}
        )
        with self.assertRaisesRegex(ToolArgumentError, "READ_ONLY_MODE"):
            ToolPermissionPolicy(paths, mode=ApprovalMode.READ_ONLY).evaluate(request)

        decision = ToolPermissionPolicy(paths, mode=ApprovalMode.AUTO_EDIT).evaluate(request)
        self.assertFalse(decision.requires_approval)
        self.assertEqual(decision.explanation.action, PolicyAction.ALLOW)

    def test_untrusted_workspace_cannot_approve_local_process_without_isolation(self) -> None:
        paths = WorkspacePaths.create(self.test_root).ensure()
        policy = ToolPermissionPolicy(
            paths,
            mode=ApprovalMode.AUTO_EDIT,
            workspace_trust=WorkspaceTrust.UNTRUSTED,
        )
        with self.assertRaisesRegex(ToolArgumentError, "PROCESS_ISOLATION_REQUIRED"):
            policy.evaluate(self.request("test.run", {"profile": "unit"}, "TESTING"))

    def test_process_command_is_validated_then_approval_gated_in_every_edit_mode(self) -> None:
        paths = WorkspacePaths.create(self.test_root).ensure()
        request = self.request(
            "process.run",
            {
                "executable": "python",
                "arguments": ["-B", "-m", "unittest", "discover", "-s", "tests"],
            },
            "TESTING",
        )

        decision = ToolPermissionPolicy(
            paths, mode=ApprovalMode.AUTO_EDIT
        ).evaluate(request)

        self.assertTrue(decision.requires_approval)
        self.assertEqual(decision.explanation.reason_code, "PROCESS_APPROVAL_REQUIRED")
        self.assertEqual(
            decision.normalized_arguments["command"][:3],
            ["python", "-B", "-m"],
        )

    def test_invalid_or_untrusted_process_is_denied_before_approval(self) -> None:
        paths = WorkspacePaths.create(self.test_root).ensure()
        unsafe = self.request(
            "process.run",
            {"executable": "python", "arguments": ["-c", "print('no')"]},
            "TESTING",
        )
        with self.assertRaisesRegex(ToolArgumentError, "registered test modules"):
            ToolPermissionPolicy(paths).evaluate(unsafe)

        valid = self.request(
            "process.run",
            {"executable": "python", "arguments": ["-m", "unittest"]},
            "TESTING",
        )
        with self.assertRaisesRegex(ToolArgumentError, "PROCESS_ISOLATION_REQUIRED"):
            ToolPermissionPolicy(
                paths, workspace_trust=WorkspaceTrust.UNTRUSTED
            ).evaluate(valid)

    def test_legacy_custom_spec_cannot_silently_lose_approval(self) -> None:
        (self.test_root / "module.py").write_text("value = 1\n", encoding="utf-8")
        legacy = ToolSpec(
            "repo.read_file",
            ToolCategory.READ,
            True,
            True,
            frozenset({"EDITING"}),
        )
        policy = ToolPermissionPolicy(
            WorkspacePaths.create(self.test_root).ensure(),
            specs=(legacy,),
            mode=ApprovalMode.AUTO_EDIT,
        )

        decision = policy.evaluate(
            self.request("repo.read_file", {"path": "module.py"})
        )

        self.assertTrue(decision.requires_approval)
        self.assertEqual(decision.explanation.reason_code, "LEGACY_APPROVAL_REQUIRED")

    def test_test_tool_is_limited_to_testing_states(self) -> None:
        with self.assertRaises(ToolStateError):
            self.make_policy().evaluate(self.request("test.run", {"profile": "unit"}))

    def test_unknown_tool_is_denied(self) -> None:
        with self.assertRaises(UnknownToolError):
            self.make_policy().evaluate(self.request("shell.exec", {"command": "whoami"}))


if __name__ == "__main__":
    unittest.main()
