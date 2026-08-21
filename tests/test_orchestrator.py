from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path
from typing import Sequence

from coding_agent.llm.provider import LLMMessage, LLMResponse
from coding_agent.models.decisions import ImplementationPlan, ImplementationStep
from coding_agent.models.records import TestExecution
from coding_agent.models.task_state import CodingTaskState
from coding_agent.storage.workspace import WorkspacePaths
from coding_agent.tools.executor import ToolExecutor
from coding_agent.tools.policy import ToolPermissionPolicy
from coding_agent.skills.catalog import SkillCatalog
from coding_agent.skills.router import SkillRouter
from coding_agent.workflow.orchestrator import CodingWorkflowOrchestrator, OrchestrationError
from coding_agent.workflow.status import WorkflowStatus

from tests.support import WorkspaceTestCase


class FixtureProvider:
    provider_name = "phase4-fixture"

    def __init__(self, responses: list[dict[str, object]]) -> None:
        self.responses = [json.dumps(item) for item in responses]

    def complete(self, messages: Sequence[LLMMessage]) -> LLMResponse:
        del messages
        if not self.responses:
            raise AssertionError("fixture provider exhausted")
        return LLMResponse(self.responses.pop(0), "fixture-model")


class OrchestratorTests(WorkspaceTestCase):
    def test_end_to_end_fixture_completes_with_grounded_diff_and_test(self) -> None:
        for skill in ("fix", "scout", "ck-plan", "cook", "test", "code-review", "git"):
            self.write_skill(skill)
        fixture = self.test_root / "tests" / "fixtures" / "sample_repo"
        fixture.mkdir(parents=True)
        for package in (self.test_root / "tests", self.test_root / "tests" / "fixtures", fixture):
            (package / "__init__.py").write_text("", encoding="utf-8")
        app = fixture / "app.py"
        app.write_text(
            "def greet(name: str) -> str:\n"
            "    return f\"Hello, {name}\"\n",
            encoding="utf-8",
        )
        test_file = fixture / "test_app.py"
        test_file.write_text(
            "from __future__ import annotations\n"
            "import sys\n"
            "import unittest\n"
            "from pathlib import Path\n"
            "sys.path.insert(0, str(Path(__file__).parent))\n"
            "from app import greet\n\n"
            "class GreetingTests(unittest.TestCase):\n"
            "    def test_greet(self) -> None:\n"
            "        self.assertEqual(greet(\"Agent\"), \"Hello, Agent\")\n",
            encoding="utf-8",
        )
        original = app.read_bytes()
        expected_digest = hashlib.sha256(original).hexdigest()
        patch = (
            "@@ -1,2 +1,3 @@\n"
            " def greet(name: str) -> str:\n"
            "+    \"\"\"Return the fixture greeting.\"\"\"\n"
            "     return f\"Hello, {name}\"\n"
        )
        state = CodingTaskState.create("Document the greeting helper", "fixture", task_id="phase4-e2e")
        state.current_status = WorkflowStatus.ANALYZING
        state.validate()
        paths = WorkspacePaths.create(self.test_root).ensure()
        executor = ToolExecutor(ToolPermissionPolicy(paths))
        router = SkillRouter(SkillCatalog(self.test_root / ".claude" / "skills").load())
        provider = FixtureProvider(
            [
                {
                    "task_type": "feature",
                    "problem": "The greeting helper needs a concise docstring.",
                    "expected_behavior": "The helper keeps its behavior and documents its purpose.",
                    "acceptance_criteria": ["fixture test passes"],
                    "search_queries": ["missing-token", "greet"],
                    "risks": [],
                },
                {
                    "objective": "Document the greeting helper",
                    "steps": [
                        {
                            "id": "step-read",
                            "action": "read",
                            "file": "tests/fixtures/sample_repo/app.py",
                            "description": "Read the grounded implementation before editing.",
                            "dependencies": [],
                            "verification_method": "confirm the source digest remains current",
                        },
                        {
                            "id": "step-modify",
                            "action": "modify",
                            "file": "tests/fixtures/sample_repo/app.py",
                            "description": "Add a docstring without changing behavior.",
                            "dependencies": ["step-read"],
                            "verification_method": "run fixture and unit profiles",
                        }
                    ],
                    "evidence_citations": ["tests/fixtures/sample_repo/app.py:1-2"],
                    "expected_tests": ["fixture"],
                    "risks": [],
                },
                {
                    "tool_name": "repo.read_file",
                    "arguments": {"path": "tests/fixtures/sample_repo/app.py"},
                    "rationale": "Read the current implementation for the first plan step.",
                    "requires_approval": False,
                },
                {
                    "tool_name": "repo.apply_patch",
                    "arguments": {
                        "path": "tests/fixtures/sample_repo/app.py",
                        "patch": patch,
                        "expected_sha256": expected_digest,
                    },
                    "rationale": "Apply the grounded documentation-only patch.",
                    "requires_approval": True,
                },
                {"approved": True, "findings": [], "summary": "The documentation patch is safe."},
                {
                    "status": "completed",
                    "summary": "Phase 4 fixture completed with grounded evidence and passing tests.",
                    "modified_files": ["tests/fixtures/sample_repo/app.py"],
                    "tests_passed": True,
                    "citations": ["tests/fixtures/sample_repo/app.py:1-3"],
                    "unresolved_findings": [],
                },
            ]
        )
        result = CodingWorkflowOrchestrator(
            state,
            provider,
            executor,
            maximum_steps=12,
            approval_handler=lambda current_state, request: True,
            skill_router=router,
        ).run()
        self.assertEqual(result.status, WorkflowStatus.COMPLETED)
        self.assertEqual(state.current_status, WorkflowStatus.COMPLETED)
        self.assertEqual(state.modified_files, ["tests/fixtures/sample_repo/app.py"])
        self.assertTrue(state.retrieved_evidence)
        self.assertEqual(state.retrieval_queries, ["missing-token", "greet"])
        self.assertEqual(state.current_plan_step_index, 2)
        self.assertEqual(state.completed_plan_step_ids, ["step-read", "step-modify"])
        self.assertEqual([item.target for item in state.test_results], ["fixture", "unit"])
        self.assertEqual(state.active_skill.name, "git")
        self.assertIn("Return the fixture greeting", app.read_text(encoding="utf-8"))

    def test_debug_decision_records_root_cause_before_repair(self) -> None:
        state = CodingTaskState.create("Repair failure", "fixture", task_id="debug-e2e")
        state.current_status = WorkflowStatus.DEBUGGING
        state.implementation_plan = ImplementationPlan(
            "Repair safely",
            [ImplementationStep("step-1", "modify", "module.py", "Apply repair")],
        )
        state.current_plan_step_index = 1
        state.completed_plan_step_ids = ["step-1"]
        state.test_results.append(TestExecution(["python"], "unit", 1, 0, 1, 2, "", "failed"))
        state.validate()
        executor = ToolExecutor(
            ToolPermissionPolicy(WorkspacePaths.create(self.test_root).ensure())
        )
        provider = FixtureProvider(
            [
                {
                    "root_cause": "The null guard is missing.",
                    "evidence": ["tests/test_module.py::test_none"],
                    "next_action": "edit",
                    "rationale": "Apply one bounded repair.",
                    "search_queries": [],
                }
            ]
        )
        orchestrator = CodingWorkflowOrchestrator(state, provider, executor)
        orchestrator._debug()
        self.assertEqual(state.current_status, WorkflowStatus.EDITING)
        self.assertEqual(state.debug_root_cause, "The null guard is missing.")
        self.assertEqual(state.debug_action, "edit")
        self.assertTrue(state.pending_repair)
        self.assertEqual(state.current_repair_iteration, 1)

    def test_plan_step_rejects_mismatched_tool_before_execution(self) -> None:
        state = CodingTaskState.create("Guard plan", "fixture", task_id="plan-guard")
        state.current_status = WorkflowStatus.EDITING
        state.implementation_plan = ImplementationPlan(
            "Modify only",
            [ImplementationStep("step-1", "modify", "module.py", "Patch module")],
        )
        state.validate()
        executor = ToolExecutor(
            ToolPermissionPolicy(WorkspacePaths.create(self.test_root).ensure())
        )
        provider = FixtureProvider(
            [
                {
                    "tool_name": "repo.create_file",
                    "arguments": {"path": "other.py", "content": "value = 1\n"},
                    "rationale": "This does not match the plan.",
                    "requires_approval": True,
                }
            ]
        )
        orchestrator = CodingWorkflowOrchestrator(state, provider, executor)
        with self.assertRaisesRegex(OrchestrationError, "does not match plan action"):
            orchestrator._edit()
        self.assertEqual(state.current_plan_step_index, 0)
        self.assertFalse(state.completed_plan_step_ids)

    def test_passing_test_step_advances_to_remaining_plan_work(self) -> None:
        state = CodingTaskState.create("Continue plan", "fixture", task_id="test-step")
        state.current_status = WorkflowStatus.TESTING
        state.implementation_plan = ImplementationPlan(
            "Verify then inspect",
            [
                ImplementationStep("verify", "test", "tests", "Run tests"),
                ImplementationStep("inspect", "read", "module.py", "Inspect result", ["verify"]),
            ],
        )
        state.test_results.append(TestExecution(["python"], "unit", 0, 1, 0, 2, "", ""))
        state.validate()
        executor = ToolExecutor(
            ToolPermissionPolicy(WorkspacePaths.create(self.test_root).ensure())
        )
        orchestrator = CodingWorkflowOrchestrator(state, FixtureProvider([]), executor)
        orchestrator._advance_after_tests()
        self.assertEqual(state.current_status, WorkflowStatus.EDITING)
        self.assertEqual(state.current_plan_step_index, 1)
        self.assertEqual(state.completed_plan_step_ids, ["verify"])

    def test_review_rejection_opens_bounded_repair(self) -> None:
        state = CodingTaskState.create("Repair review", "fixture", task_id="review-repair")
        state.current_status = WorkflowStatus.REVIEWING
        state.implementation_plan = ImplementationPlan(
            "Review safely",
            [ImplementationStep("step-1", "modify", "module.py", "Apply change")],
        )
        state.current_plan_step_index = 1
        state.completed_plan_step_ids = ["step-1"]
        state.test_results.append(TestExecution(["python"], "unit", 0, 1, 0, 2, "", ""))
        state.validate()
        executor = ToolExecutor(
            ToolPermissionPolicy(WorkspacePaths.create(self.test_root).ensure())
        )
        provider = FixtureProvider(
            [
                {
                    "approved": False,
                    "summary": "A medium issue needs repair.",
                    "findings": [
                        {
                            "severity": "medium",
                            "finding_type": "correctness",
                            "file": "module.py",
                            "line": 1,
                            "description": "Handle the edge case.",
                            "suggested_fix": "Add a guard.",
                        }
                    ],
                }
            ]
        )
        orchestrator = CodingWorkflowOrchestrator(state, provider, executor)
        orchestrator._review()
        self.assertEqual(state.current_status, WorkflowStatus.EDITING)
        self.assertTrue(state.pending_repair)


if __name__ == "__main__":
    unittest.main()
