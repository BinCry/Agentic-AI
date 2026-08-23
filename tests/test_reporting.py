from __future__ import annotations

import unittest

from coding_agent.models.decisions import (
    AnalysisCompletionResult,
    ImplementationPlan,
    ImplementationStep,
    ReviewFinding,
    TaskCompletionResult,
)
from coding_agent.models.records import RepositoryEvidence, TestExecution
from coding_agent.models.task_state import CodingTaskState
from coding_agent.workflow.reporting import (
    FinalReportError,
    build_analysis_report,
    build_final_report,
)


class FinalReportingTests(unittest.TestCase):
    def test_builds_read_only_analysis_report_and_rejects_mutation(self) -> None:
        state = CodingTaskState.create("Analyze only", "repo", task_id="analysis-report")
        state.task_type = "analysis"
        state.read_only = True
        state.retrieved_evidence = [
            RepositoryEvidence("c1", "module.py", 1, 1, "VALUE = 1", 1.0, "exact")
        ]
        completion = AnalysisCompletionResult(
            "completed",
            "The module defines VALUE.",
            "The conclusion is grounded in the retrieved declaration.",
            ["module.py:1-1"],
            [],
        )

        report = build_analysis_report(state, completion)

        self.assertIn("read-only", report.changes[0].lower())
        self.assertIn("not run", report.tests[0].lower())
        ungrounded = AnalysisCompletionResult(
            "completed",
            completion.summary,
            completion.reasoning,
            ["missing.py:1-1"],
            [],
        )
        with self.assertRaisesRegex(FinalReportError, "not grounded"):
            build_analysis_report(state, ungrounded)
        state.modified_files = ["module.py"]
        with self.assertRaisesRegex(FinalReportError, "cannot contain repository mutations"):
            build_analysis_report(state, completion)

    def test_read_only_analysis_accepts_posix_citation_for_legacy_windows_evidence(self) -> None:
        state = CodingTaskState.create("Analyze only", "repo", task_id="windows-citation")
        state.task_type = "analysis"
        state.read_only = True
        state.retrieved_evidence = [
            RepositoryEvidence(
                "c1",
                r"plans\phase-02-controlled-mcp-tools.md",
                1,
                57,
                "# Phase 02",
                1.0,
                "exact",
            )
        ]
        completion = AnalysisCompletionResult(
            "completed",
            "The plan describes controlled tools.",
            "The conclusion uses the retrieved plan evidence.",
            ["plans/phase-02-controlled-mcp-tools.md:45-53"],
            [],
        )

        report = build_analysis_report(state, completion)

        self.assertEqual(
            report.evidence,
            ["plans/phase-02-controlled-mcp-tools.md:45-53"],
        )

    def make_state(self) -> CodingTaskState:
        state = CodingTaskState.create("Fix the parser", "repo", task_id="report-task")
        state.normalized_problem_statement = "The parser accepts an invalid empty token."
        state.modified_files = ["src/parser.py"]
        state.implementation_plan = ImplementationPlan(
            "Reject invalid input",
            [
                ImplementationStep(
                    "patch-parser",
                    "modify",
                    "src/parser.py",
                    "Reject an empty token before parsing.",
                )
            ],
        )
        state.test_results = [
            TestExecution(["python"], "unit", 0, 3, 0, 12, "ok", "")
        ]
        state.review_summary = "The patch is minimal and safe."
        return state

    def make_completion(self, **overrides: object) -> TaskCompletionResult:
        values = {
            "status": "completed",
            "summary": "The parser now rejects empty tokens.",
            "reasoning": "The missing input guard was the root cause.",
            "modified_files": ["src/parser.py"],
            "tests_passed": True,
            "citations": ["src/parser.py:1-8"],
            "unresolved_findings": [],
            "pr_summary": "",
        }
        values.update(overrides)
        return TaskCompletionResult(**values)

    def test_builds_all_required_sections_from_verified_state(self) -> None:
        state = self.make_state()
        state.review_findings.append(
            ReviewFinding(
                "low",
                "portability",
                "src/parser.py",
                3,
                "The alternate runtime is not available in CI.",
                "Add the runtime to a future CI matrix.",
            )
        )
        report = build_final_report(state, self.make_completion())
        payload = report.to_dict()
        self.assertEqual(
            set(payload),
            {
                "status",
                "summary",
                "root_cause_or_reasoning",
                "changes",
                "tests",
                "review",
                "evidence",
                "remaining_limitations",
            },
        )
        self.assertIn("Reject an empty token", report.changes[0])
        self.assertIn("3 passed", report.tests[0])
        self.assertIn("alternate runtime", report.remaining_limitations[0])
        markdown = report.to_markdown()
        for heading in (
            "Summary",
            "Root Cause / Reasoning",
            "Changes",
            "Tests",
            "Review",
            "Evidence",
            "Remaining Limitations",
        ):
            self.assertIn(f"## {heading}", markdown)

    def test_rejects_model_file_claim_that_conflicts_with_tool_state(self) -> None:
        with self.assertRaisesRegex(FinalReportError, "do not match"):
            build_final_report(
                self.make_state(),
                self.make_completion(modified_files=["src/unrelated.py"]),
            )

    def test_rejects_success_when_current_test_batch_failed(self) -> None:
        state = self.make_state()
        state.test_results = [
            TestExecution(["python"], "unit", 1, 2, 1, 10, "", "failed")
        ]
        with self.assertRaisesRegex(FinalReportError, "passing current tests"):
            build_final_report(state, self.make_completion())


if __name__ == "__main__":
    unittest.main()
