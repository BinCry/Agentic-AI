from __future__ import annotations

import hashlib
import json
import unittest
from unittest.mock import patch

from coding_agent.models.decisions import ImplementationPlan, ImplementationStep
from coding_agent.models.records import RepositoryEvidence
from coding_agent.models.task_state import CodingTaskState
from coding_agent.storage.checkpoint_store import CheckpointStore
from coding_agent.storage.workspace import WorkspacePaths
from coding_agent.tools.contracts import ToolRequest
from coding_agent.tools.executor import ToolExecutor
from coding_agent.tools.policy import ToolPermissionPolicy
from coding_agent.workflow.status import WorkflowStatus
from coding_agent.workflow.context import ContextCompactor, ContextProjector

from tests.support import WorkspaceTestCase


class RecoveryTests(WorkspaceTestCase):
    def make_state(self) -> CodingTaskState:
        state = CodingTaskState.create("Recover safely", "fixture", task_id="recovery-task")
        state.current_status = WorkflowStatus.EDITING
        state.implementation_plan = ImplementationPlan(
            "recover",
            [ImplementationStep("step-1", "modify", "module.py", "patch", [])],
        )
        state.validate()
        return state

    def test_checkpoint_restores_state_and_file_bytes(self) -> None:
        target = self.test_root / "module.py"
        target.write_bytes(b"value = 1\r\n")
        state = self.make_state()
        paths = WorkspacePaths.create(self.test_root).ensure()
        store = CheckpointStore(paths)

        record = store.create(state, "before risky patch", file_paths=("module.py",))
        target.write_bytes(b"value = 2\n")
        state.current_status = WorkflowStatus.FAILED

        restored = store.restore(state.task_id, record.checkpoint_id)
        self.assertEqual(restored.current_status, WorkflowStatus.EDITING)
        self.assertEqual(target.read_bytes(), b"value = 1\r\n")
        self.assertEqual(restored.checkpoints[-1].checkpoint_id, record.checkpoint_id)

    def test_context_projection_is_bounded_and_valid_json(self) -> None:
        state = CodingTaskState.create("Compact this context", "fixture", task_id="context-task")
        state.retrieved_evidence = []
        state.original_issue = "x" * 10_000
        projected = ContextProjector(ContextCompactor(1_000)).project(state, "IssueAnalysis")
        self.assertLessEqual(len(projected), 1_000)
        self.assertTrue(json.loads(projected)["truncated"])

    def test_context_projection_prioritizes_grounded_evidence_score(self) -> None:
        state = CodingTaskState.create("Prioritize evidence", "fixture", task_id="evidence-task")
        state.retrieved_evidence = [
            RepositoryEvidence("low", "low.py", 1, 1, "low\n", 0.1, "lexical", "a" * 64),
            RepositoryEvidence("high", "high.py", 1, 1, "high\n", 0.9, "lexical+symbol", "b" * 64),
        ]
        payload = json.loads(ContextProjector().project(state, "ImplementationPlan"))
        self.assertEqual([item["chunk_id"] for item in payload["evidence"]], ["high", "low"])
        self.assertEqual(payload["evidence"][0]["score"], 0.9)

    def test_checkpoint_failure_does_not_enter_pending_approval(self) -> None:
        target = self.test_root / "module.py"
        target.write_text("value = 1\n", encoding="utf-8")
        state = self.make_state()
        paths = WorkspacePaths.create(self.test_root).ensure()
        executor = ToolExecutor(ToolPermissionPolicy(paths))
        state.retrieved_evidence.append(executor.rag.retrieve_grounded("value = 1")[0].evidence)
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

        with patch.object(executor.checkpoints, "_atomic_write", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                executor.request_execution(state, request)
        self.assertEqual(state.current_status, WorkflowStatus.EDITING)
        self.assertIsNone(state.pending_tool_call)

    def test_approved_tool_is_written_to_durable_ledger(self) -> None:
        target = self.test_root / "module.py"
        target.write_text("value = 1\n", encoding="utf-8")
        state = self.make_state()
        paths = WorkspacePaths.create(self.test_root).ensure()
        executor = ToolExecutor(ToolPermissionPolicy(paths))
        state.retrieved_evidence.append(executor.rag.retrieve_grounded("value = 1")[0].evidence)
        request = ToolRequest(
            "patch-approval",
            state.task_id,
            "repo.apply_patch",
            {
                "path": "module.py",
                "patch": "@@ -1 +1 @@\n-value = 1\n+value = 2\n",
                "expected_sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
            },
            WorkflowStatus.EDITING.value,
        )
        pending = executor.request_execution(state, request)
        self.assertEqual(pending.error_code, "APPROVAL_REQUIRED")
        result = executor.approve_and_execute(state, request)
        self.assertTrue(result.success)
        ledger = executor.approvals.load(state.task_id)
        self.assertEqual([item.decision for item in ledger], ["approved"])
        self.assertEqual(state.approval_decisions[-1].arguments_hash, request.arguments_hash())


if __name__ == "__main__":
    unittest.main()
