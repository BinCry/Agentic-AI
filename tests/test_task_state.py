from __future__ import annotations

import unittest

from coding_agent.models.decisions import ImplementationPlan, ImplementationStep, ReviewFinding
from coding_agent.models.records import ActiveSkill, RepositoryEvidence, TestExecution
from coding_agent.models.task_state import CodingTaskState
from coding_agent.models.validation import ModelValidationError
from coding_agent.workflow.status import WorkflowStatus


class CodingTaskStateTests(unittest.TestCase):
    def test_create_validates_identity_and_defaults(self) -> None:
        state = CodingTaskState.create("Fix the parser", "repo", task_id="task-01")
        self.assertEqual(state.current_status, WorkflowStatus.CREATED)
        self.assertEqual(state.task_id, "task-01")

    def test_round_trip_preserves_nested_models(self) -> None:
        state = CodingTaskState.create("Add a feature", "repo", task_id="round-trip")
        state.current_status = WorkflowStatus.PLANNING
        state.active_skill = ActiveSkill(
            "ck-plan", ".claude/skills/ck-plan/SKILL.md", "a" * 64
        )
        state.retrieved_evidence.append(
            RepositoryEvidence("chunk-1", "src/app.py", 1, 5, "content", 0.9, "lexical")
        )
        state.implementation_plan = ImplementationPlan(
            objective="Add feature",
            steps=[ImplementationStep("s1", "modify", "src/app.py", "Implement", [])],
        )
        restored = CodingTaskState.from_dict(state.to_dict())
        self.assertEqual(restored.to_dict(), state.to_dict())
        self.assertEqual(restored.retrieved_evidence[0].chunk_id, "chunk-1")

    def test_rejects_unsafe_task_id(self) -> None:
        with self.assertRaisesRegex(ModelValidationError, "unsafe"):
            CodingTaskState.create("Issue", "repo", task_id="../escape")

    def test_rejects_counter_above_maximum(self) -> None:
        state = CodingTaskState.create("Issue", "repo")
        state.current_iteration = state.maximum_iterations + 1
        with self.assertRaisesRegex(ModelValidationError, "iteration bounds"):
            state.validate()

    def test_persisted_state_rejects_boolean_counter_and_unknown_schema(self) -> None:
        payload = CodingTaskState.create("Issue", "repo").to_dict()
        payload["current_iteration"] = True
        with self.assertRaisesRegex(ModelValidationError, "iteration bounds"):
            CodingTaskState.from_dict(payload)
        payload = CodingTaskState.create("Issue", "repo").to_dict()
        payload["schema_version"] = 99
        with self.assertRaisesRegex(ModelValidationError, "unsupported schema"):
            CodingTaskState.from_dict(payload)

    def test_persisted_state_rejects_malformed_nested_record(self) -> None:
        payload = CodingTaskState.create("Issue", "repo").to_dict()
        payload["test_results"] = [
            {
                "command": ["python"],
                "target": "tests",
                "exit_code": 0,
                "passed_count": -1,
                "failed_count": 0,
                "duration_ms": 1,
                "stdout_summary": "",
                "stderr_summary": "",
                "timed_out": False,
            }
        ]
        with self.assertRaisesRegex(ModelValidationError, "passed_count"):
            CodingTaskState.from_dict(payload)

    def test_plan_step_verification_and_progress_round_trip(self) -> None:
        state = CodingTaskState.create("Issue", "repo")
        state.implementation_plan = ImplementationPlan(
            objective="Implement safely",
            steps=[
                ImplementationStep(
                    "s1",
                    "modify",
                    "src/app.py",
                    "Implement change",
                    [],
                    "run the focused unit test",
                )
            ],
        )
        state.current_plan_step_index = 1
        state.completed_plan_step_ids = ["s1"]
        state.current_status = WorkflowStatus.EDITING
        state.validate()
        restored = CodingTaskState.from_dict(state.to_dict())
        self.assertEqual(restored.current_plan_step_index, 1)
        self.assertEqual(restored.completed_plan_step_ids, ["s1"])
        self.assertEqual(
            restored.implementation_plan.steps[0].verification_method,
            "run the focused unit test",
        )

    def test_persisted_state_rejects_forged_terminal_and_waiting_states(self) -> None:
        payload = CodingTaskState.create("Issue", "repo").to_dict()
        payload["current_status"] = "COMPLETED"
        with self.assertRaisesRegex(ModelValidationError, "COMPLETED requires"):
            CodingTaskState.from_dict(payload)
        payload = CodingTaskState.create("Issue", "repo").to_dict()
        payload["current_status"] = "WAITING_APPROVAL"
        with self.assertRaisesRegex(ModelValidationError, "approval_return_status"):
            CodingTaskState.from_dict(payload)

    def test_waiting_for_finalization_rejects_blocking_review_finding(self) -> None:
        state = CodingTaskState.create("Issue", "repo")
        state.current_status = WorkflowStatus.WAITING_APPROVAL
        state.approval_return_status = WorkflowStatus.FINALIZING
        state.implementation_plan = ImplementationPlan(
            "Implement",
            [ImplementationStep("s1", "modify", "src/app.py", "Implement", [])],
        )
        state.test_results = [
            TestExecution(["python"], "tests", 0, 1, 0, 1, "ok", "")
        ]
        state.review_findings = [
            ReviewFinding("high", "correctness", "src/app.py", 1, "Broken", "Fix")
        ]
        with self.assertRaisesRegex(ModelValidationError, "blocking review"):
            CodingTaskState.from_dict(state.to_dict())


if __name__ == "__main__":
    unittest.main()
