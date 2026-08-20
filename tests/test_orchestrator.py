from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path
from typing import Sequence

from coding_agent.llm.provider import LLMMessage, LLMResponse
from coding_agent.models.task_state import CodingTaskState
from coding_agent.storage.workspace import WorkspacePaths
from coding_agent.tools.executor import ToolExecutor
from coding_agent.tools.policy import ToolPermissionPolicy
from coding_agent.skills.catalog import SkillCatalog
from coding_agent.skills.router import SkillRouter
from coding_agent.workflow.orchestrator import CodingWorkflowOrchestrator
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
                    "search_queries": ["greet"],
                    "risks": [],
                },
                {
                    "objective": "Document the greeting helper",
                    "steps": [
                        {
                            "id": "step-1",
                            "action": "modify",
                            "file": "tests/fixtures/sample_repo/app.py",
                            "description": "Add a docstring without changing behavior.",
                            "dependencies": [],
                        }
                    ],
                    "evidence_citations": ["tests/fixtures/sample_repo/app.py:1-2"],
                    "expected_tests": ["fixture"],
                    "risks": [],
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
        self.assertEqual(state.test_results[-1].target, "fixture")
        self.assertEqual(state.active_skill.name, "git")
        self.assertIn("Return the fixture greeting", app.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
