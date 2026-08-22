from __future__ import annotations

import unittest

from coding_agent.models.decisions import ImplementationPlan, ImplementationStep
from coding_agent.models.task_state import CodingTaskState
from coding_agent.storage.workspace import WorkspacePaths
from coding_agent.tools.contracts import ToolRequest
from coding_agent.tools.executor import ToolExecutor
from coding_agent.tools.policy import ToolPermissionPolicy
from coding_agent.workflow.runtime import _approve_pending
from coding_agent.workflow.status import WorkflowStatus

from tests.support import WorkspaceTestCase


class WorkflowAutoApprovalTests(WorkspaceTestCase):
    def test_explicit_auto_approval_executes_persisted_pending_request(self) -> None:
        paths = WorkspacePaths.create(self.test_root).ensure()
        executor = ToolExecutor(ToolPermissionPolicy(paths))
        state = CodingTaskState.create("Create module", "fixture", task_id="auto-approval")
        state.current_status = WorkflowStatus.EDITING
        state.implementation_plan = ImplementationPlan(
            "Create module",
            [ImplementationStep("create", "create", "new.py", "Create the module")],
        )
        request = ToolRequest(
            "plan-create",
            state.task_id,
            "repo.create_file",
            {"path": "new.py", "content": "value = 1\n"},
            state.current_status.value,
        )
        waiting = executor.request_execution(state, request)
        self.assertFalse(waiting.success)
        self.assertEqual(state.current_status, WorkflowStatus.WAITING_APPROVAL)

        _approve_pending(executor, state)

        self.assertEqual(state.current_status, WorkflowStatus.EDITING)
        self.assertIsNone(state.pending_tool_call)
        self.assertEqual((self.test_root / "new.py").read_text(encoding="utf-8"), "value = 1\n")


if __name__ == "__main__":
    unittest.main()
