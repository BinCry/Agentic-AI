from __future__ import annotations

import hashlib
import io
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from typing import Sequence
from unittest.mock import patch

from coding_agent.cli import main
from coding_agent.llm.openai_client import OpenAIConfigurationError
from coding_agent.llm.openrouter_provider import OpenRouterConfigurationError
from coding_agent.llm.provider import LLMMessage, LLMResponse
from coding_agent.models.task_state import CodingTaskState
from coding_agent.rag.index import RepositoryIndex
from coding_agent.storage.task_store import JsonTaskStore
from coding_agent.storage.workspace import WorkspacePaths
from coding_agent.workflow.engine import WorkflowEngine
from coding_agent.workflow.runtime import run_workflow
from coding_agent.workflow.status import WorkflowStatus

from tests.support import WorkspaceTestCase


class FixtureProvider:
    provider_name = "runtime-fixture"

    def __init__(self, responses: list[dict[str, object]]) -> None:
        self.responses = [json.dumps(item) for item in responses]

    def complete(self, messages: Sequence[LLMMessage]) -> LLMResponse:
        del messages
        if not self.responses:
            raise AssertionError("fixture provider exhausted")
        return LLMResponse(self.responses.pop(0), "fixture-model")


class WorkflowRuntimeTests(WorkspaceTestCase):
    def run_cli(self, *arguments: str) -> tuple[int, dict[str, object], str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = main(["--workspace", str(self.test_root), *arguments])
        payload = json.loads(stdout.getvalue()) if stdout.getvalue() else {}
        return code, payload, stderr.getvalue()

    def write_runtime_skills(self) -> None:
        for name in ("fix", "scout", "ck-plan", "cook", "test", "code-review", "git"):
            self.write_skill(name)

    def test_missing_provider_configuration_returns_json_error_without_task(self) -> None:
        self.write_skill("fix")
        with patch(
            "coding_agent.workflow.runtime.OpenAIResponsesProvider.from_env",
            side_effect=OpenAIConfigurationError("OPENAI_API_KEY is required"),
        ):
            code, payload, error = self.run_cli("run", "--issue", "Fix configuration")
        self.assertEqual((code, payload), (1, {}))
        self.assertEqual(json.loads(error)["error"], "OpenAIConfigurationError")
        paths = WorkspacePaths.create(self.test_root).ensure()
        self.assertEqual(JsonTaskStore(paths).list_task_ids(), ())

    def test_run_accepts_explicit_external_read_only_skill_root(self) -> None:
        workspace = self.test_root / "target-repository"
        skill_root = self.test_root / "shared-skills"
        workspace.mkdir()
        skill_file = skill_root / "fix" / "SKILL.md"
        skill_file.parent.mkdir(parents=True)
        skill_file.write_text(
            "---\nname: fix\ndescription: test skill\nkeywords: [test]\n---\n",
            encoding="utf-8",
        )
        paths = WorkspacePaths.create(workspace).ensure()
        store = JsonTaskStore(paths)

        outcome = run_workflow(
            paths,
            store,
            issue="Analyze target",
            skill_root=str(skill_root),
            provider=FixtureProvider([{}, {}, {}]),
        )

        self.assertEqual(outcome.result.status, WorkflowStatus.FAILED)
        self.assertIn("IssueAnalysis", outcome.result.reason)

    def test_openrouter_provider_selection_uses_its_environment_contract(self) -> None:
        self.write_skill("fix")
        with patch(
            "coding_agent.workflow.runtime.OpenRouterResponsesProvider.from_env",
            side_effect=OpenRouterConfigurationError("OPENROUTER_API_KEY is required"),
        ):
            code, payload, error = self.run_cli(
                "run",
                "--issue",
                "Fix configuration",
                "--model-provider",
                "openrouter",
            )
        self.assertEqual((code, payload), (1, {}))
        self.assertEqual(json.loads(error)["error"], "OpenRouterConfigurationError")
        paths = WorkspacePaths.create(self.test_root).ensure()
        self.assertEqual(JsonTaskStore(paths).list_task_ids(), ())

    def test_invalid_model_output_persists_failed_state(self) -> None:
        self.write_skill("fix")
        provider = FixtureProvider([{}, {}, {}])
        with patch(
            "coding_agent.workflow.runtime.OpenAIResponsesProvider.from_env",
            return_value=provider,
        ):
            code, payload, error = self.run_cli("run", "--issue", "Return invalid output")
        self.assertEqual((code, error), (2, ""))
        self.assertEqual(payload["status"], "FAILED")
        state = JsonTaskStore(WorkspacePaths.create(self.test_root).ensure()).load(
            str(payload["task_id"])
        )
        self.assertEqual(state.current_status, WorkflowStatus.FAILED)
        self.assertIn("task_type", state.errors[-1].message)
        self.assertIsNotNone(state.project_profile)
        self.assertEqual(state.project_profile.workspace_name, self.test_root.name)
        self.assertEqual(state.usage_ledger.model_calls, 3)
        self.assertEqual(state.usage_ledger.usage_unknown_calls, 3)
        self.assertEqual(state.usage_ledger.total_tokens_known_calls, 0)
        self.assertEqual(state.usage_ledger.latency_known_calls, 3)

    def test_read_only_analysis_completes_without_mutation_or_tests(self) -> None:
        self.write_runtime_skills()
        module = self.test_root / "module.py"
        original = "VALUE = 1\n"
        module.write_text(original, encoding="utf-8")
        provider = FixtureProvider(
            [
                {
                    "task_type": "feature",
                    "problem": "Explain the repository structure without changing files.",
                    "expected_behavior": "Return a grounded read-only analysis.",
                    "acceptance_criteria": ["Cite repository evidence", "Do not modify files"],
                    "search_queries": ["VALUE"],
                    "risks": ["Do not enter mutation or test stages"],
                },
                {
                    "status": "completed",
                    "summary": "The repository contains a single VALUE module.",
                    "reasoning": "Grounded retrieval found the module declaration.",
                    "citations": ["module.py:1-1"],
                    "unresolved_findings": [],
                },
            ]
        )

        with patch(
            "coding_agent.workflow.runtime.OpenAIResponsesProvider.from_env",
            return_value=provider,
        ):
            code, payload, error = self.run_cli(
                "run",
                "--issue",
                "Analyze the repository structure without changing files",
                "--read-only",
            )

        self.assertEqual((code, error), (0, ""))
        self.assertEqual(payload["status"], "COMPLETED")
        state = JsonTaskStore(WorkspacePaths.create(self.test_root).ensure()).load(
            str(payload["task_id"])
        )
        self.assertEqual(state.task_type, "analysis")
        self.assertTrue(state.read_only)
        self.assertEqual(state.modified_files, [])
        self.assertEqual(state.test_results, [])
        self.assertIsNone(state.implementation_plan)
        self.assertEqual(module.read_text(encoding="utf-8"), original)
        self.assertIn("read-only", state.final_report.changes[0].lower())

    def test_read_only_rejects_auto_approve_before_creating_task(self) -> None:
        self.write_skill("fix")

        code, payload, error = self.run_cli(
            "run",
            "--issue",
            "Analyze only",
            "--read-only",
            "--auto-approve",
        )

        self.assertEqual((code, payload), (1, {}))
        self.assertIn("cannot be combined", json.loads(error)["message"])
        paths = WorkspacePaths.create(self.test_root).ensure()
        self.assertEqual(JsonTaskStore(paths).list_task_ids(), ())

    def test_persisted_read_only_task_rejects_auto_approve_on_resume(self) -> None:
        self.write_skill("fix")
        paths = WorkspacePaths.create(self.test_root).ensure()
        state = CodingTaskState.create(
            "Analyze only", "fixture", task_id="read-only-resume", read_only=True
        )
        WorkflowEngine(state).transition(WorkflowStatus.ANALYZING, "ready")
        JsonTaskStore(paths).save(state)

        with patch(
            "coding_agent.workflow.runtime.OpenAIResponsesProvider.from_env",
            return_value=FixtureProvider([]),
        ):
            code, payload, error = self.run_cli(
                "run",
                "--task-id",
                state.task_id,
                "--auto-approve",
            )

        self.assertEqual((code, payload), (1, {}))
        self.assertIn("not valid", json.loads(error)["message"])

    def test_default_pause_external_approval_and_resume_to_completion(self) -> None:
        self.write_runtime_skills()
        module = self.test_root / "module.py"
        module.write_text("VALUE = 1\n", encoding="utf-8")
        tests = self.test_root / "tests"
        tests.mkdir()
        (tests / "test_module.py").write_text(
            "import unittest\n"
            "from module import VALUE\n\n"
            "class ValueTests(unittest.TestCase):\n"
            "    def test_value(self):\n"
            "        self.assertEqual(VALUE, 2)\n",
            encoding="utf-8",
        )
        digest = hashlib.sha256(module.read_bytes()).hexdigest()
        patch_text = "@@ -1 +1 @@\n-VALUE = 1\n+VALUE = 2\n"
        start_provider = FixtureProvider(
            [
                {
                    "task_type": "bug_fix",
                    "problem": "VALUE must be two.",
                    "expected_behavior": "The module exports VALUE = 2.",
                    "acceptance_criteria": ["unit test passes"],
                    "search_queries": ["VALUE"],
                    "risks": [],
                },
                {
                    "objective": "Correct VALUE",
                    "steps": [
                        {
                            "id": "change-value",
                            "action": "modify",
                            "file": "module.py",
                            "description": "Set VALUE to two.",
                            "dependencies": [],
                            "verification_method": "run unit tests",
                        }
                    ],
                    "evidence_citations": ["module.py:1-1"],
                    "expected_tests": ["unit"],
                    "risks": [],
                },
                {
                    "tool_name": "repo.apply_patch",
                    "arguments": {
                        "path": "module.py",
                        "patch": patch_text,
                        "expected_sha256": digest,
                    },
                    "rationale": "Apply the grounded one-line fix.",
                    "requires_approval": True,
                },
            ]
        )
        with patch(
            "coding_agent.workflow.runtime.OpenAIResponsesProvider.from_env",
            return_value=start_provider,
        ):
            code, waiting, error = self.run_cli("run", "--issue", "Set VALUE to two")
        self.assertEqual((code, error), (3, ""))
        self.assertEqual(waiting["status"], "WAITING_APPROVAL")
        self.assertTrue(waiting["requires_approval"])
        self.assertEqual(module.read_text(encoding="utf-8"), "VALUE = 1\n")

        task_id = str(waiting["task_id"])
        paths = WorkspacePaths.create(self.test_root).ensure()
        paused_state = JsonTaskStore(paths).load(task_id)
        module_evidence = [item for item in paused_state.retrieved_evidence if item.path == "module.py"]
        self.assertTrue(module_evidence, [item.path for item in paused_state.retrieved_evidence])
        self.assertTrue(
            RepositoryIndex(paths).verify_evidence(module_evidence[0]),
            (module_evidence[0], module.read_bytes(), digest),
        )
        code, approved, error = self.run_cli(
            "approve-tool",
            "--task-id",
            task_id,
            "--request-id",
            "plan-change-value",
        )
        self.assertEqual((code, error), (0, ""), approved)
        self.assertTrue(approved["success"])
        self.assertEqual(module.read_text(encoding="utf-8"), "VALUE = 2\n")

        finish_provider = FixtureProvider(
            [
                {"approved": True, "findings": [], "summary": "The one-line fix is safe."},
                {
                    "status": "completed",
                    "summary": "VALUE now matches the required behavior.",
                    "reasoning": "Grounded patch and unit test confirm the correction.",
                    "modified_files": ["module.py"],
                    "tests_passed": True,
                    "citations": ["module.py:1-1"],
                    "unresolved_findings": [],
                },
            ]
        )
        with patch(
            "coding_agent.workflow.runtime.OpenAIResponsesProvider.from_env",
            return_value=finish_provider,
        ):
            code, completed, error = self.run_cli(
                "run", "--task-id", task_id, "--auto-approve"
            )
        self.assertEqual((code, error), (0, ""))
        self.assertEqual(completed["status"], "COMPLETED")
        state = JsonTaskStore(WorkspacePaths.create(self.test_root).ensure()).load(task_id)
        self.assertEqual(state.completed_plan_step_ids, ["change-value"])
        self.assertEqual(state.current_status, WorkflowStatus.COMPLETED)


if __name__ == "__main__":
    unittest.main()
