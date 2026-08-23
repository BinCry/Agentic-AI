from __future__ import annotations

import unittest

from coding_agent.models.decisions import ImplementationPlan, ImplementationStep, ReviewFinding
from coding_agent.models.records import FinalReport, RepositoryEvidence, TestExecution
from coding_agent.models.task_state import CodingTaskState
from coding_agent.workflow.engine import (
    InvalidTransitionError,
    TransitionPreconditionError,
    WorkflowEngine,
)
from coding_agent.workflow.status import WorkflowStatus


class WorkflowEngineTests(unittest.TestCase):
    def make_engine(self, **limits: int) -> WorkflowEngine:
        return WorkflowEngine(CodingTaskState.create("Issue", "repo", **limits))

    @staticmethod
    def add_plan(engine: WorkflowEngine) -> None:
        engine.state.implementation_plan = ImplementationPlan(
            objective="Implement",
            steps=[ImplementationStep("s1", "modify", "src/app.py", "Implement", [])],
        )

    @staticmethod
    def add_passing_test(engine: WorkflowEngine) -> None:
        engine.state.test_results.append(
            TestExecution(["python", "-m", "unittest"], "tests", 0, 1, 0, 5, "ok", "")
        )

    @staticmethod
    def add_completion_evidence(engine: WorkflowEngine) -> None:
        engine.state.acceptance_criteria = ["Tests pass"]
        engine.state.retrieved_evidence = [
            RepositoryEvidence("c1", "src/app.py", 1, 1, "code", 1.0, "exact")
        ]
        engine.state.modified_files = ["src/app.py"]

    def test_happy_path_reaches_completed(self) -> None:
        engine = self.make_engine()
        for target in (
            WorkflowStatus.ANALYZING,
            WorkflowStatus.RETRIEVING,
            WorkflowStatus.VERIFYING_EVIDENCE,
            WorkflowStatus.PLANNING,
        ):
            engine.transition(target, "test")
        self.add_plan(engine)
        engine.transition(WorkflowStatus.EDITING, "test")
        engine.transition(WorkflowStatus.TESTING, "test")
        self.add_passing_test(engine)
        engine.transition(WorkflowStatus.REVIEWING, "test")
        engine.transition(WorkflowStatus.FINALIZING, "test")
        engine.state.final_summary = "Completed safely"
        engine.state.final_diff = "diff --git a/src/app.py b/src/app.py"
        engine.state.pr_summary = "Completed safely"
        engine.state.final_citations = ["src/app.py:L1-L1"]
        engine.state.final_report = FinalReport(
            "completed",
            "Completed safely",
            "The verified implementation satisfies the acceptance criteria.",
            ["src/app.py: Implement"],
            ["tests: PASS (1 passed, 0 failed, 5 ms)"],
            ["Approved: no blocking findings."],
            ["src/app.py:L1-L1"],
            ["No known limitations."],
        )
        self.add_completion_evidence(engine)
        engine.transition(WorkflowStatus.COMPLETED, "test")
        self.assertEqual(engine.state.current_status, WorkflowStatus.COMPLETED)
        self.assertEqual(engine.state.current_iteration, 9)

    def test_read_only_analysis_reaches_completed_without_coding_artifacts(self) -> None:
        engine = self.make_engine()
        engine.state.task_type = "analysis"
        engine.state.read_only = True
        engine.transition(WorkflowStatus.ANALYZING, "test")
        engine.transition(WorkflowStatus.RETRIEVING, "test")
        engine.state.acceptance_criteria = ["Cite repository evidence"]
        engine.state.retrieved_evidence = [
            RepositoryEvidence("c1", "module.py", 1, 1, "VALUE = 1", 1.0, "exact")
        ]
        engine.transition(WorkflowStatus.VERIFYING_EVIDENCE, "test")
        engine.transition(WorkflowStatus.FINALIZING, "read-only evidence verified")
        engine.state.final_summary = "The module defines VALUE."
        engine.state.final_citations = ["module.py:1-1"]
        engine.state.final_report = FinalReport(
            "completed",
            engine.state.final_summary,
            "Grounded repository analysis.",
            ["No repository files changed; this was a read-only analysis."],
            ["Not run; read-only analysis does not enter testing."],
            ["Mutation review was not required."],
            engine.state.final_citations,
            ["No known limitations."],
        )

        engine.transition(WorkflowStatus.COMPLETED, "analysis complete")

        self.assertEqual(engine.state.current_status, WorkflowStatus.COMPLETED)
        self.assertIsNone(engine.state.implementation_plan)
        self.assertFalse(engine.state.modified_files)
        self.assertFalse(engine.state.test_results)

    def test_coding_task_cannot_use_read_only_finalization_transition(self) -> None:
        engine = self.make_engine()
        engine.transition(WorkflowStatus.ANALYZING, "test")
        engine.transition(WorkflowStatus.RETRIEVING, "test")
        engine.transition(WorkflowStatus.VERIFYING_EVIDENCE, "test")

        with self.assertRaisesRegex(TransitionPreconditionError, "read_only"):
            engine.transition(WorkflowStatus.FINALIZING, "skip coding stages")

        self.assertEqual(engine.state.current_status, WorkflowStatus.VERIFYING_EVIDENCE)

    def test_invalid_transition_is_rejected(self) -> None:
        engine = self.make_engine()
        with self.assertRaises(InvalidTransitionError):
            engine.transition(WorkflowStatus.EDITING, "skip analysis")

    def test_explicit_failure_records_reason(self) -> None:
        engine = self.make_engine()
        engine.transition(WorkflowStatus.FAILED, "invalid task input")
        self.assertEqual(engine.state.current_status, WorkflowStatus.FAILED)
        self.assertEqual(engine.state.errors[-1].code, "TASK_FAILED")
        self.assertEqual(engine.state.errors[-1].message, "invalid task input")

    def test_editing_requires_an_implementation_plan(self) -> None:
        engine = self.make_engine()
        for target in (
            WorkflowStatus.ANALYZING,
            WorkflowStatus.RETRIEVING,
            WorkflowStatus.VERIFYING_EVIDENCE,
            WorkflowStatus.PLANNING,
        ):
            engine.transition(target, "test")
        with self.assertRaisesRegex(TransitionPreconditionError, "plan"):
            engine.transition(WorkflowStatus.EDITING, "missing plan")

    def test_review_and_completion_require_evidence(self) -> None:
        engine = self.make_engine()
        for target in (
            WorkflowStatus.ANALYZING,
            WorkflowStatus.RETRIEVING,
            WorkflowStatus.VERIFYING_EVIDENCE,
            WorkflowStatus.PLANNING,
        ):
            engine.transition(target, "test")
        self.add_plan(engine)
        engine.transition(WorkflowStatus.EDITING, "test")
        engine.transition(WorkflowStatus.TESTING, "test")
        with self.assertRaisesRegex(TransitionPreconditionError, "passing test"):
            engine.transition(WorkflowStatus.REVIEWING, "untested")
        self.add_passing_test(engine)
        engine.transition(WorkflowStatus.REVIEWING, "tested")
        engine.state.review_findings.append(
            ReviewFinding("high", "correctness", "src/app.py", 1, "Broken", "Fix it")
        )
        with self.assertRaisesRegex(TransitionPreconditionError, "blocking review"):
            engine.transition(WorkflowStatus.FINALIZING, "unresolved")

    def test_completion_requires_acceptance_repository_and_file_evidence(self) -> None:
        engine = self.make_engine()
        for target in (
            WorkflowStatus.ANALYZING,
            WorkflowStatus.RETRIEVING,
            WorkflowStatus.VERIFYING_EVIDENCE,
            WorkflowStatus.PLANNING,
        ):
            engine.transition(target, "test")
        self.add_plan(engine)
        engine.transition(WorkflowStatus.EDITING, "test")
        engine.transition(WorkflowStatus.TESTING, "test")
        self.add_passing_test(engine)
        engine.transition(WorkflowStatus.REVIEWING, "test")
        engine.transition(WorkflowStatus.FINALIZING, "test")
        engine.state.final_summary = "Done"
        with self.assertRaisesRegex(TransitionPreconditionError, "acceptance criteria"):
            engine.transition(WorkflowStatus.COMPLETED, "incomplete evidence")

    def test_completion_requires_structured_final_report(self) -> None:
        engine = self.make_engine()
        for target in (
            WorkflowStatus.ANALYZING,
            WorkflowStatus.RETRIEVING,
            WorkflowStatus.VERIFYING_EVIDENCE,
            WorkflowStatus.PLANNING,
        ):
            engine.transition(target, "test")
        self.add_plan(engine)
        engine.transition(WorkflowStatus.EDITING, "test")
        engine.transition(WorkflowStatus.TESTING, "test")
        self.add_passing_test(engine)
        engine.transition(WorkflowStatus.REVIEWING, "test")
        engine.transition(WorkflowStatus.FINALIZING, "test")
        self.add_completion_evidence(engine)
        engine.state.final_summary = "Done"
        engine.state.final_diff = "diff --git a/src/app.py b/src/app.py"
        engine.state.pr_summary = "Done"
        engine.state.final_citations = ["src/app.py:L1-L1"]
        with self.assertRaisesRegex(TransitionPreconditionError, "structured final report"):
            engine.transition(WorkflowStatus.COMPLETED, "missing report")

    def test_retrieval_requires_explicit_evidence_verification_stage(self) -> None:
        engine = self.make_engine()
        engine.transition(WorkflowStatus.ANALYZING, "analysis")
        engine.transition(WorkflowStatus.RETRIEVING, "retrieve")
        engine.transition(WorkflowStatus.VERIFYING_EVIDENCE, "evidence retrieved")
        self.assertEqual(engine.state.current_status, WorkflowStatus.VERIFYING_EVIDENCE)
        engine.transition(WorkflowStatus.PLANNING, "evidence verified")
        self.assertEqual(engine.state.current_status, WorkflowStatus.PLANNING)

    def test_latest_repair_test_batch_can_supersede_historical_failure(self) -> None:
        engine = self.make_engine()
        for target in (
            WorkflowStatus.ANALYZING,
            WorkflowStatus.RETRIEVING,
            WorkflowStatus.VERIFYING_EVIDENCE,
            WorkflowStatus.PLANNING,
        ):
            engine.transition(target, "test")
        self.add_plan(engine)
        engine.transition(WorkflowStatus.EDITING, "test")
        engine.transition(WorkflowStatus.TESTING, "first test")
        engine.state.test_results.append(
            TestExecution(["python"], "tests", 1, 0, 1, 5, "", "failed")
        )
        engine.transition(WorkflowStatus.DEBUGGING, "repair")
        engine.transition(WorkflowStatus.EDITING, "fixed")
        engine.transition(WorkflowStatus.TESTING, "retest")
        self.add_passing_test(engine)
        engine.transition(WorkflowStatus.REVIEWING, "latest batch passed")
        self.assertEqual(engine.state.current_status, WorkflowStatus.REVIEWING)

    def test_iteration_limit_forces_failure_without_overflow(self) -> None:
        engine = self.make_engine(maximum_iterations=1)
        engine.transition(WorkflowStatus.ANALYZING, "first")
        result = engine.transition(WorkflowStatus.RETRIEVING, "second")
        self.assertTrue(result.forced_failure)
        self.assertEqual(engine.state.current_status, WorkflowStatus.FAILED)
        self.assertEqual(engine.state.current_iteration, 1)
        self.assertEqual(engine.state.errors[-1].code, "MAX_ITERATIONS")

    def test_repair_limit_forces_failure(self) -> None:
        engine = self.make_engine(maximum_repair_iterations=1)
        for target in (
            WorkflowStatus.ANALYZING,
            WorkflowStatus.RETRIEVING,
            WorkflowStatus.VERIFYING_EVIDENCE,
            WorkflowStatus.PLANNING,
        ):
            engine.transition(target, "test")
        self.add_plan(engine)
        for target in (
            WorkflowStatus.EDITING,
            WorkflowStatus.TESTING,
            WorkflowStatus.DEBUGGING,
            WorkflowStatus.EDITING,
            WorkflowStatus.TESTING,
            WorkflowStatus.DEBUGGING,
        ):
            engine.transition(target, "test")
        result = engine.transition(WorkflowStatus.EDITING, "second repair")
        self.assertTrue(result.forced_failure)
        self.assertEqual(engine.state.errors[-1].code, "MAX_REPAIR_ITERATIONS")

    def test_retrieval_retries_are_bounded(self) -> None:
        engine = self.make_engine(maximum_retrieval_retries=1)
        engine.transition(WorkflowStatus.ANALYZING, "test")
        engine.transition(WorkflowStatus.RETRIEVING, "test")
        self.assertTrue(engine.record_retrieval_failure("first"))
        self.assertFalse(engine.record_retrieval_failure("second"))
        self.assertEqual(engine.state.retrieval_retry_count, 1)
        self.assertEqual(engine.state.current_status, WorkflowStatus.FAILED)

    def test_retrieval_failure_cannot_mutate_terminal_task(self) -> None:
        engine = self.make_engine()
        engine.transition(WorkflowStatus.FAILED, "terminal")
        with self.assertRaisesRegex(InvalidTransitionError, "only while retrieving"):
            engine.record_retrieval_failure("late failure")

    def test_approval_round_trip(self) -> None:
        engine = self.make_engine()
        for target in (
            WorkflowStatus.ANALYZING,
            WorkflowStatus.RETRIEVING,
            WorkflowStatus.VERIFYING_EVIDENCE,
            WorkflowStatus.PLANNING,
        ):
            engine.transition(target, "test")
        self.add_plan(engine)
        engine.request_approval(WorkflowStatus.EDITING, "needs consent")
        self.assertEqual(engine.state.current_status, WorkflowStatus.WAITING_APPROVAL)
        engine.approve()
        self.assertEqual(engine.state.current_status, WorkflowStatus.EDITING)
        self.assertIsNone(engine.state.approval_return_status)

    def test_test_approval_resume_preserves_current_test_batch(self) -> None:
        engine = self.make_engine()
        for target in (
            WorkflowStatus.ANALYZING,
            WorkflowStatus.RETRIEVING,
            WorkflowStatus.VERIFYING_EVIDENCE,
            WorkflowStatus.PLANNING,
        ):
            engine.transition(target, "test")
        self.add_plan(engine)
        engine.transition(WorkflowStatus.EDITING, "test")
        engine.transition(WorkflowStatus.TESTING, "test")
        engine.state.test_results.append(TestExecution(["python"], "fixture", 0, 1, 0, 1, "", ""))
        engine.request_approval(WorkflowStatus.TESTING, "run broad tests")
        engine.approve()
        self.assertEqual(engine.state.current_status, WorkflowStatus.TESTING)
        self.assertEqual(engine.state.test_run_start_index, 0)
        self.assertIsNone(engine.state.approval_return_status)

    def test_invalid_approval_request_does_not_mutate_return_status(self) -> None:
        engine = self.make_engine()
        with self.assertRaises(InvalidTransitionError):
            engine.request_approval(WorkflowStatus.EDITING, "too early")
        self.assertIsNone(engine.state.approval_return_status)

    def test_waiting_approval_cannot_be_bypassed_by_direct_transition(self) -> None:
        engine = self.make_engine()
        for target in (
            WorkflowStatus.ANALYZING,
            WorkflowStatus.RETRIEVING,
            WorkflowStatus.VERIFYING_EVIDENCE,
            WorkflowStatus.PLANNING,
        ):
            engine.transition(target, "test")
        self.add_plan(engine)
        engine.request_approval(WorkflowStatus.EDITING, "needs consent")
        with self.assertRaisesRegex(InvalidTransitionError, "approve"):
            engine.transition(WorkflowStatus.EDITING, "bypass")
        self.assertEqual(engine.state.current_status, WorkflowStatus.WAITING_APPROVAL)


if __name__ == "__main__":
    unittest.main()
