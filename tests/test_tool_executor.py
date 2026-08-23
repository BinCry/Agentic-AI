from __future__ import annotations

import hashlib
import unittest
from unittest.mock import patch

from coding_agent.errors import ErrorCode
from coding_agent.models.decisions import ImplementationPlan, ImplementationStep
from coding_agent.models.records import TestExecution
from coding_agent.models.task_state import CodingTaskState
from coding_agent.policy.models import ApprovalMode
from coding_agent.storage.checkpoint_store import CheckpointStore
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

    def test_auto_edit_mutation_runs_without_prompt_but_keeps_checkpoint(self) -> None:
        state = self.make_state()
        paths = WorkspacePaths.create(self.test_root).ensure()
        executor = ToolExecutor(
            ToolPermissionPolicy(paths, mode=ApprovalMode.AUTO_EDIT)
        )
        request = ToolRequest(
            "create-auto",
            state.task_id,
            "repo.create_file",
            {"path": "new.py", "content": "x = 1\n"},
            WorkflowStatus.EDITING.value,
        )

        result = executor.request_execution(state, request)

        self.assertTrue(result.success)
        self.assertIsNone(state.pending_tool_call)
        self.assertEqual((self.test_root / "new.py").read_text(encoding="utf-8"), "x = 1\n")
        self.assertEqual(len(CheckpointStore(paths).list_records(state.task_id)), 1)

    def test_invalid_tool_call_is_rejected_and_traced(self) -> None:
        state = self.make_state()
        result = self.make_executor().request_execution(
            state,
            ToolRequest(
                "invalid-1",
                state.task_id,
                "shell.exec",
                {},
                WorkflowStatus.EDITING.value,
            ),
        )
        self.assertFalse(result.success)
        self.assertEqual(result.error_code, "TOOL_REQUEST_INVALID")
        self.assertEqual(state.tool_execution_trace[-1].result_metadata["error_code"], "TOOL_REQUEST_INVALID")

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

    def test_empty_retrieval_uses_structured_error_code(self) -> None:
        state = self.make_state()
        state.current_status = WorkflowStatus.RETRIEVING
        state.validate()
        result = self.make_executor().request_execution(
            state,
            ToolRequest(
                "retrieve-empty",
                state.task_id,
                "repo.retrieve",
                {"query": "definitely-missing-symbol", "top_k": 3},
                WorkflowStatus.RETRIEVING.value,
            ),
        )
        self.assertEqual(result.error_code, ErrorCode.RETRIEVAL_EMPTY.value)
        self.assertEqual(state.errors[-1].code, ErrorCode.RETRIEVAL_EMPTY.value)
        self.assertTrue(state.errors[-1].recoverable)

    def test_access_boundary_uses_access_denied_code(self) -> None:
        state = self.make_state()
        result = self.make_executor().request_execution(
            state,
            ToolRequest(
                "read-escape",
                state.task_id,
                "repo.read_file",
                {"path": "../outside.py"},
                WorkflowStatus.EDITING.value,
            ),
        )
        self.assertEqual(result.error_code, ErrorCode.ACCESS_DENIED.value)
        self.assertEqual(state.errors[-1].code, ErrorCode.ACCESS_DENIED.value)
        self.assertFalse(state.errors[-1].recoverable)

    def test_patch_conflict_is_recoverable_and_typed(self) -> None:
        target = self.test_root / "module.py"
        target.write_text("value = 1\n", encoding="utf-8")
        state = self.make_state()
        executor = self.make_executor()
        state.retrieved_evidence.append(executor.rag.retrieve_grounded("value = 1")[0].evidence)
        request = ToolRequest(
            "patch-conflict",
            state.task_id,
            "repo.apply_patch",
            {
                "path": "module.py",
                "patch": "@@ -1 +1 @@\n-value = 1\n+value = 2\n",
                "expected_sha256": "0" * 64,
            },
            WorkflowStatus.EDITING.value,
        )
        executor.request_execution(state, request)
        result = executor.approve_and_execute(state, request)
        self.assertEqual(result.error_code, ErrorCode.PATCH_CONFLICT.value)
        self.assertEqual(state.errors[-1].code, ErrorCode.PATCH_CONFLICT.value)
        self.assertTrue(state.errors[-1].recoverable)

    def test_failed_and_timed_out_tests_have_distinct_codes(self) -> None:
        cases = (
            (
                TestExecution(["python"], "unit", 1, 0, 1, 2, "", "failed"),
                ErrorCode.TEST_FAILED,
            ),
            (
                TestExecution(["python"], "unit", 1, 0, 0, 2, "", "timeout", True),
                ErrorCode.TEST_TIMEOUT,
            ),
        )
        for execution, expected_code in cases:
            with self.subTest(expected_code=expected_code.value):
                state = self.make_state()
                state.current_status = WorkflowStatus.TESTING
                state.validate()
                executor = self.make_executor()
                request = ToolRequest(
                    f"test-{expected_code.value.lower()}",
                    state.task_id,
                    "test.run",
                    {"profile": "unit"},
                    WorkflowStatus.TESTING.value,
                )
                with patch.object(executor.tests, "run", return_value=execution):
                    executor.request_execution(state, request)
                    result = executor.approve_and_execute(state, request)
                self.assertEqual(result.error_code, expected_code.value)
                self.assertEqual(state.errors[-1].code, expected_code.value)
                self.assertTrue(state.errors[-1].recoverable)


if __name__ == "__main__":
    unittest.main()
