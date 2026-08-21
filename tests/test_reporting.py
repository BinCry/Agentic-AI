from __future__ import annotations

import unittest

from coding_agent.models.decisions import (
    ImplementationPlan,
    ImplementationStep,
    ReviewFinding,
    TaskCompletionResult,
)
from coding_agent.models.records import TestExecution
from coding_agent.models.task_state import CodingTaskState
from coding_agent.workflow.reporting import FinalReportError, build_final_report


class FinalReportingTests(unittest.TestCase):
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
