from __future__ import annotations

import unittest
from typing import Sequence

from coding_agent.errors import ErrorCode
from coding_agent.llm.provider import LLMMessage, LLMResponse
from coding_agent.models.decisions import ImplementationPlan, ImplementationStep
from coding_agent.models.records import ApprovalDecisionRecord, TestExecution, ToolTraceRecord
from coding_agent.models.task_state import CodingTaskState
from coding_agent.storage.workspace import WorkspacePaths
from coding_agent.tools.contracts import ToolRequest
from coding_agent.tools.executor import ToolExecutor
from coding_agent.tools.policy import ToolPermissionPolicy
from coding_agent.workflow.orchestrator import CodingWorkflowOrchestrator
from coding_agent.workflow.status import WorkflowStatus

from tests.support import WorkspaceTestCase


class NeverProvider:
    provider_name = "never"

    def complete(self, messages: Sequence[LLMMessage]) -> LLMResponse:
        del messages
        raise AssertionError("provider should not be called")


class OrchestratorResumeTests(WorkspaceTestCase):
    def orchestrator(self, state: CodingTaskState) -> CodingWorkflowOrchestrator:
        paths = WorkspacePaths.create(self.test_root).ensure()
        return CodingWorkflowOrchestrator(
            state,
            NeverProvider(),
            ToolExecutor(ToolPermissionPolicy(paths)),
        )

    def test_persisted_failed_test_resumes_into_debugging(self) -> None:
        state = CodingTaskState.create("Fix test", "fixture", task_id="resume-test")
        state.current_status = WorkflowStatus.TESTING
        state.implementation_plan = ImplementationPlan(
            "Fix test",
            [ImplementationStep("change", "modify", "module.py", "Apply fix")],
        )
        state.current_plan_step_index = 1
        state.completed_plan_step_ids = ["change"]
        state.test_results = [
            TestExecution(["python"], "unit", 1, 0, 1, 5, "", "failed")
        ]

        self.assertTrue(self.orchestrator(state)._test())
        self.assertEqual(state.current_status, WorkflowStatus.DEBUGGING)

    def test_persisted_patch_conflict_resumes_into_retrieval(self) -> None:
        state = CodingTaskState.create("Fix conflict", "fixture", task_id="resume-patch")
        state.current_status = WorkflowStatus.EDITING
        state.implementation_plan = ImplementationPlan(
            "Fix conflict",
            [ImplementationStep("change", "modify", "module.py", "Apply fix")],
        )
        request = ToolRequest(
            "plan-change",
            state.task_id,
            "repo.apply_patch",
            {
                "path": "module.py",
                "patch": "@@ -1 +1 @@\n-old\n+new\n",
                "expected_sha256": "a" * 64,
            },
            WorkflowStatus.EDITING.value,
        )
        timestamp = "2026-08-22T00:00:00+00:00"
        state.approval_decisions.append(
            ApprovalDecisionRecord(
                request.request_id,
                request.task_id,
                request.tool_name,
                request.arguments_hash(),
                "approved",
                request.workflow_state,
                "approved",
                timestamp,
            )
        )
        state.tool_execution_trace.append(
            ToolTraceRecord(
                "event-1",
                timestamp,
                request.workflow_state,
                None,
                request.tool_name,
                False,
                1,
                {"arguments_hash": request.arguments_hash()},
                {"error_code": ErrorCode.PATCH_CONFLICT.value},
                "source changed",
            )
        )

        self.assertTrue(self.orchestrator(state)._resume_approved_edit())
        self.assertEqual(state.current_status, WorkflowStatus.RETRIEVING)
        self.assertEqual(state.retrieval_queries[0], "module.py")


if __name__ == "__main__":
    unittest.main()
