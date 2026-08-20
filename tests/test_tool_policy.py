from __future__ import annotations

import unittest

from coding_agent.storage.workspace import WorkspacePaths
from coding_agent.tools.contracts import ToolRequest
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

    def test_test_tool_is_limited_to_testing_states(self) -> None:
        with self.assertRaises(ToolStateError):
            self.make_policy().evaluate(self.request("test.run", {"profile": "unit"}))

    def test_unknown_tool_is_denied(self) -> None:
        with self.assertRaises(UnknownToolError):
            self.make_policy().evaluate(self.request("shell.exec", {"command": "whoami"}))


if __name__ == "__main__":
    unittest.main()
