from __future__ import annotations

import unittest

from coding_agent.models.decisions import (
    ImplementationPlan,
    IssueAnalysis,
    ReviewResult,
    TaskCompletionResult,
)
from coding_agent.models.validation import ModelValidationError


class DecisionModelTests(unittest.TestCase):
    def test_issue_analysis_accepts_complete_payload(self) -> None:
        model = IssueAnalysis.from_dict(
            {
                "task_type": "bug_fix",
                "problem": "A command fails.",
                "expected_behavior": "The command succeeds.",
                "acceptance_criteria": ["Exit code is zero"],
                "search_queries": ["command entrypoint"],
                "risks": [],
            }
        )
        self.assertEqual(model.task_type, "bug_fix")
        self.assertEqual(model.to_dict()["acceptance_criteria"], ["Exit code is zero"])

    def test_issue_analysis_rejects_missing_acceptance_criteria(self) -> None:
        with self.assertRaises(ModelValidationError):
            IssueAnalysis.from_dict(
                {
                    "task_type": "feature",
                    "problem": "Need a feature.",
                    "expected_behavior": "Feature works.",
                    "acceptance_criteria": [],
                    "search_queries": [],
                    "risks": [],
                }
            )

    def test_plan_rejects_forward_dependency(self) -> None:
        with self.assertRaisesRegex(ModelValidationError, "forward dependencies"):
            ImplementationPlan.from_dict(
                {
                    "objective": "Implement safely",
                    "steps": [
                        {
                            "id": "step-1",
                            "action": "modify",
                            "file": "src/app.py",
                            "description": "Change app",
                            "dependencies": ["step-2"],
                        },
                        {
                            "id": "step-2",
                            "action": "test",
                            "file": "tests/test_app.py",
                            "description": "Test app",
                            "dependencies": [],
                        },
                    ],
                    "evidence_citations": [],
                    "expected_tests": [],
                    "risks": [],
                }
            )

    def test_approved_review_rejects_high_findings(self) -> None:
        with self.assertRaisesRegex(ModelValidationError, "approved review"):
            ReviewResult.from_dict(
                {
                    "approved": True,
                    "summary": "Not actually safe",
                    "findings": [
                        {
                            "severity": "high",
                            "finding_type": "security",
                            "file": "src/app.py",
                            "line": 4,
                            "description": "Unsafe operation",
                            "suggested_fix": "Add validation",
                        }
                    ],
                }
            )

    def test_completed_result_requires_passing_tests(self) -> None:
        with self.assertRaisesRegex(ModelValidationError, "passing tests"):
            TaskCompletionResult.from_dict(
                {
                    "status": "completed",
                    "summary": "Done",
                    "modified_files": ["src/app.py"],
                    "tests_passed": False,
                    "citations": [],
                    "unresolved_findings": [],
                }
            )


if __name__ == "__main__":
    unittest.main()
