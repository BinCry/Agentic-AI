from __future__ import annotations

import json
import unittest

from coding_agent.models.decisions import ImplementationPlan, ImplementationStep
from coding_agent.models.records import RepositoryEvidence
from coding_agent.models.task_state import CodingTaskState
from coding_agent.storage.observation_store import ObservationStore
from coding_agent.storage.workspace import WorkspacePaths
from coding_agent.workflow.context import ContextCompactor, ContextProjector
from coding_agent.workflow.context_budget import (
    ContextBudget,
    ContextBudgeter,
    ContextSection,
)

from tests.support import WorkspaceTestCase


class ContextBudgeterTests(unittest.TestCase):
    def test_budget_and_section_contracts_reject_ambiguous_values(self) -> None:
        with self.assertRaisesRegex(ValueError, "positive integers"):
            ContextBudget(maximum_tokens=True, maximum_chars=100)
        with self.assertRaisesRegex(ValueError, "priority"):
            ContextSection("section", {}, True)
        duplicate = [
            ContextSection("same", "first", 1),
            ContextSection("same", "second", 2),
        ]
        with self.assertRaisesRegex(ValueError, "unique"):
            ContextBudgeter().project(
                duplicate, ContextBudget(maximum_tokens=100, maximum_chars=300)
            )

    def test_required_citation_fallback_precedes_optional_history(self) -> None:
        sections = [
            ContextSection("decision", "ReviewResult", 100, required=True),
            ContextSection(
                "evidence",
                [{"path": "module.py", "lines": [1, 4], "content": "x" * 2_000}],
                80,
                required=True,
                fallback=[
                    {
                        "path": "module.py",
                        "lines": [1, 4],
                        "digest": "a" * 64,
                    }
                ],
            ),
            ContextSection("observations", [{"summary": "test failed"}], 60),
            ContextSection("history", ["y" * 2_000], 10),
        ]
        budget = ContextBudget(maximum_tokens=180, maximum_chars=540)

        projected = ContextBudgeter().project(sections, budget)

        self.assertEqual(projected.payload["evidence"][0]["path"], "module.py")
        self.assertNotIn("content", projected.payload["evidence"][0])
        self.assertNotIn("history", projected.payload)
        self.assertTrue(projected.truncated)
        self.assertLessEqual(projected.serialized_chars, budget.maximum_chars)
        self.assertLessEqual(projected.estimated_tokens, budget.maximum_tokens)

    def test_projection_is_deterministic_for_equal_priority_sections(self) -> None:
        sections = [
            ContextSection("first", "a", 10),
            ContextSection("second", "b", 10),
        ]
        budgeter = ContextBudgeter()
        budget = ContextBudget(maximum_tokens=100, maximum_chars=300)

        first = budgeter.project(sections, budget)
        second = budgeter.project(sections, budget)

        self.assertEqual(first.to_json(), second.to_json())
        self.assertEqual(first.included_sections, ("first", "second"))


class ContextProjectionTests(WorkspaceTestCase):
    def test_cited_evidence_keeps_provenance_after_content_compaction(self) -> None:
        state = CodingTaskState.create(
            "Review the grounded change", "fixture", task_id="cited-context"
        )
        state.retrieved_evidence = [
            RepositoryEvidence(
                "high",
                "high.py",
                1,
                2,
                "h" * 12_000,
                0.9,
                "hybrid",
                "b" * 64,
            ),
            RepositoryEvidence(
                "cited",
                "module.py",
                10,
                12,
                "c" * 12_000,
                0.2,
                "lexical",
                "a" * 64,
            ),
        ]
        state.implementation_plan = ImplementationPlan(
            "Review module",
            [ImplementationStep("step-1", "read", "module.py", "review")],
            evidence_citations=["module.py:10-12"],
        )

        content = ContextProjector(ContextCompactor(4_000)).project(
            state, "ReviewResult"
        )
        payload = json.loads(content)

        self.assertEqual(payload["evidence"][0]["chunk_id"], "cited")
        self.assertEqual(payload["evidence"][0]["path"], "module.py")
        self.assertEqual(payload["evidence"][0]["lines"], [10, 12])
        self.assertEqual(payload["evidence"][0]["digest"], "a" * 64)
        self.assertTrue(payload["truncated"])
        self.assertLessEqual(len(content), 4_000)

    def test_observation_projection_uses_reference_not_full_result(self) -> None:
        paths = WorkspacePaths.create(self.test_root).ensure()
        store = ObservationStore(paths)
        state = CodingTaskState.create(
            "Inspect observation", "fixture", task_id="observation-context"
        )
        record = store.append(
            state.task_id,
            "turn-1",
            "repo.read_file",
            "d" * 64,
            {"output": "secret-output-value", "success": True},
            summary="token=visible-value read completed",
        )

        content = ContextProjector(
            ContextCompactor(8_000), observation_store=store
        ).project(state, "IssueAnalysis")
        payload = json.loads(content)
        reference = payload["observations"][0]

        self.assertEqual(reference["observation_id"], record.observation_id)
        self.assertEqual(reference["artifact_path"], record.artifact_path)
        self.assertEqual(reference["result_sha256"], record.result_sha256)
        self.assertNotIn("visible-value", reference["summary"])
        self.assertNotIn("secret-output-value", content)


if __name__ == "__main__":
    unittest.main()
