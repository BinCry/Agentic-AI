from __future__ import annotations

import hashlib
import unittest

from coding_agent.models.decisions import ImplementationPlan, ImplementationStep
from coding_agent.models.task_state import CodingTaskState
from coding_agent.storage.workspace import WorkspacePaths
from coding_agent.tools.contracts import ToolRequest
from coding_agent.tools.executor import ToolExecutionError, ToolExecutor
from coding_agent.tools.policy import ToolPermissionPolicy
from coding_agent.workflow.status import WorkflowStatus

from tests.support import WorkspaceTestCase


class ToolExecutorTests(WorkspaceTestCase):
    def make_state(self) -> CodingTaskState:
        state = CodingTaskState.create("Implement tool", "fixture", task_id="tool-task")
        state.implementation_plan = ImplementationPlan(
            objective="implement tool",
            steps=[ImplementationStep("step-1", "modify", "module.py", "change module")],
        )
        state.current_status = WorkflowStatus.EDITING
        state.validate()
        return state

    def make_executor(self) -> ToolExecutor:
        return ToolExecutor(ToolPermissionPolicy(WorkspacePaths.create(self.test_root).ensure()))

    def test_mutation_requires_matching_approval_and_records_trace(self) -> None:
        target = self.test_root / "module.py"
        original = "value = 1\n"
        target.write_text(original, encoding="utf-8")
        state = self.make_state()
        request = ToolRequest(
            "patch-1",
            state.task_id,
            "repo.apply_patch",
            {
                "path": "module.py",
                "patch": "@@ -1 +1 @@\n-value = 1\n+value = 2\n",
                "expected_sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
            },
            WorkflowStatus.EDITING.value,
        )
        executor = self.make_executor()
        state.retrieved_evidence.append(executor.rag.retrieve_grounded("value = 1")[0].evidence)
        pending = executor.request_execution(state, request)
        self.assertEqual(pending.error_code, "APPROVAL_REQUIRED")
        self.assertEqual(state.current_status, WorkflowStatus.WAITING_APPROVAL)
        self.assertIsNotNone(state.pending_tool_call)

        result = executor.approve_and_execute(state, request)
        self.assertTrue(result.success)
        self.assertEqual(target.read_text(encoding="utf-8"), "value = 2\n")
        self.assertIsNone(state.pending_tool_call)
        self.assertEqual(state.modified_files, ["module.py"])
        self.assertEqual(len(state.tool_execution_trace), 1)

    def test_changed_arguments_cannot_reuse_approval(self) -> None:
        state = self.make_state()
        request = ToolRequest(
            "create-1",
            state.task_id,
            "repo.create_file",
            {"path": "new.py", "content": "x = 1\n"},
            WorkflowStatus.EDITING.value,
        )
        executor = self.make_executor()
        executor.request_execution(state, request)
        changed = ToolRequest(
            request.request_id,
            request.task_id,
            request.tool_name,
            {"path": "new.py", "content": "x = 2\n"},
            request.workflow_state,
        )
        with self.assertRaises(ToolExecutionError):
            executor.approve_and_execute(state, changed)
        self.assertFalse((self.test_root / "new.py").exists())

    def test_read_tool_runs_without_approval(self) -> None:
        target = self.test_root / "module.py"
        target.write_text("value = 1\n", encoding="utf-8")
        state = self.make_state()
        result = self.make_executor().request_execution(
            state,
            ToolRequest(
                "read-1",
                state.task_id,
                "repo.read_file",
                {"path": "module.py"},
                WorkflowStatus.EDITING.value,
            ),
        )
        self.assertTrue(result.success)
        self.assertEqual(result.output, "value = 1\n")
        self.assertEqual(state.current_status, WorkflowStatus.EDITING)

    def test_grounded_retrieval_updates_state_with_citation(self) -> None:
        target = self.test_root / "module.py"
        target.write_text("def run():\n    return 'needle'\n", encoding="utf-8")
        state = self.make_state()
        state.current_status = WorkflowStatus.RETRIEVING
        state.validate()
        result = self.make_executor().request_execution(
            state,
            ToolRequest(
                "retrieve-1",
                state.task_id,
                "repo.retrieve",
                {"query": "needle", "top_k": 3},
                WorkflowStatus.RETRIEVING.value,
            ),
        )
        self.assertTrue(result.success)
        self.assertEqual(state.retrieval_queries, ["needle"])
        self.assertTrue(state.retrieved_evidence)
        self.assertEqual(state.retrieved_evidence[0].path, "module.py")
        self.assertEqual(len(state.retrieved_evidence[0].file_digest), 64)


if __name__ == "__main__":
    unittest.main()
