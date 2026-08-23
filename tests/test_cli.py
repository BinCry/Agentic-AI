from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout

from coding_agent.cli import main
from coding_agent.models.decisions import ImplementationPlan, ImplementationStep
from coding_agent.models.records import FinalReport, RepositoryEvidence, TestExecution
from coding_agent.models.task_state import CodingTaskState
from coding_agent.storage.task_store import JsonTaskStore
from coding_agent.storage.workspace import WorkspacePaths
from coding_agent.tools.policy import DEFAULT_TOOL_SPECS
from coding_agent.workflow.status import WorkflowStatus

from tests.support import WorkspaceTestCase


class CliTests(WorkspaceTestCase):
    def run_cli(self, *arguments: str) -> tuple[int, dict[str, object], str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = main(["--workspace", str(self.test_root), *arguments])
        payload = json.loads(stdout.getvalue()) if stdout.getvalue() else {}
        return code, payload, stderr.getvalue()

    def test_init_show_and_transition(self) -> None:
        self.write_skill("fix", declared_name="ck:fix")
        self.write_skill("scout", declared_name="ck:scout")
        code, created, error = self.run_cli(
            "init", "--issue", "Fix it", "--repository", "repo", "--task-id", "cli-task"
        )
        self.assertEqual((code, error), (0, ""))
        self.assertEqual(created["current_status"], "ANALYZING")

        code, shown, error = self.run_cli("show", "--task-id", "cli-task")
        self.assertEqual((code, error), (0, ""))
        self.assertEqual(shown["task_id"], "cli-task")

        code, transitioned, error = self.run_cli(
            "transition",
            "--task-id",
            "cli-task",
            "--to",
            "RETRIEVING",
            "--reason",
            "analysis complete",
        )
        self.assertEqual((code, error), (0, ""))
        self.assertEqual(transitioned["current_status"], "RETRIEVING")
        self.assertEqual(transitioned["active_skill"]["name"], "ck:scout")

    def test_invalid_transition_returns_json_error(self) -> None:
        self.write_skill("fix")
        self.run_cli("init", "--issue", "Fix it", "--task-id", "bad-transition")
        code, payload, error = self.run_cli(
            "transition",
            "--task-id",
            "bad-transition",
            "--to",
            "EDITING",
            "--reason",
            "skip",
        )
        self.assertEqual(code, 1)
        self.assertEqual(payload, {})
        self.assertEqual(json.loads(error)["error"], "InvalidTransitionError")

    def test_project_inspect_is_model_free_and_json_serializable(self) -> None:
        (self.test_root / "pyproject.toml").write_text(
            "[project]\nname='cli-fixture'\n", encoding="utf-8"
        )
        (self.test_root / "AGENTS.md").write_text("Keep changes small", encoding="utf-8")

        code, payload, error = self.run_cli("project", "inspect", "--format", "json")

        self.assertEqual((code, error), (0, ""))
        self.assertEqual(payload["ecosystems"], ["python"])
        self.assertEqual(payload["instructions"][0]["path"], "AGENTS.md")

    def test_policy_check_explains_deny_without_execution_and_redacts_content(self) -> None:
        arguments = {
            "path": "blocked.py",
            "content": "sk-" + "x" * 24,
        }

        code, payload, error = self.run_cli(
            "policy",
            "check",
            "--tool",
            "repo.create_file",
            "--arguments-json",
            json.dumps(arguments),
            "--mode",
            "read-only",
        )

        self.assertEqual((code, error), (0, ""))
        self.assertEqual(payload["decision"]["action"], "deny")
        self.assertEqual(payload["decision"]["reason_code"], "READ_ONLY_MODE")
        self.assertEqual(payload["decision"]["arguments"]["content"], "[REDACTED]")
        self.assertFalse((self.test_root / "blocked.py").exists())
        self.assertFalse((self.test_root / ".coding-agent").exists())

    def test_policy_check_rejects_workspace_rule_that_widens_authority(self) -> None:
        policy = self.test_root / "policy.toml"
        policy.write_text(
            "version=1\n[[rules]]\nid='widen'\naction='allow'\n"
            "tool='repo.create_file'\nreason_code='WIDEN'\n",
            encoding="utf-8",
        )

        code, payload, error = self.run_cli(
            "policy",
            "check",
            "--tool",
            "git.status",
            "--workspace-policy",
            "policy.toml",
        )

        self.assertEqual((code, payload), (1, {}))
        self.assertEqual(json.loads(error)["error"], "PolicyConfigurationError")

    def test_policy_check_covers_every_registered_tool_without_side_effects(self) -> None:
        module = self.test_root / "module.py"
        module.write_text("value = 1\n", encoding="utf-8")
        cases = {
            "repo.list_files": ({}, "EDITING"),
            "repo.read_file": ({"path": "module.py"}, "EDITING"),
            "repo.search_text": ({"query": "value"}, "EDITING"),
            "repo.find_symbols": ({"path": "module.py"}, "EDITING"),
            "repo.retrieve": ({"query": "value"}, "RETRIEVING"),
            "repo.apply_patch": (
                {"path": "module.py", "patch": "patch", "expected_sha256": "0" * 64},
                "EDITING",
            ),
            "repo.create_file": ({"path": "new.py", "content": "value = 2\n"}, "EDITING"),
            "test.detect_framework": ({}, "EDITING"),
            "test.run": ({"profile": "unit"}, "TESTING"),
            "process.run": (
                {"executable": "python", "arguments": ["-m", "unittest"]},
                "TESTING",
            ),
            "git.status": ({}, "EDITING"),
            "git.diff": ({"paths": ["module.py"]}, "EDITING"),
            "git.changed_files": ({}, "EDITING"),
        }
        self.assertEqual(set(cases), {item.name for item in DEFAULT_TOOL_SPECS})

        for tool, (arguments, state) in cases.items():
            with self.subTest(tool=tool):
                code, payload, error = self.run_cli(
                    "policy",
                    "check",
                    "--tool",
                    tool,
                    "--arguments-json",
                    json.dumps(arguments),
                    "--state",
                    state,
                )
                self.assertEqual((code, error), (0, ""))
                self.assertIn(payload["decision"]["action"], {"allow", "ask"})

        self.assertEqual(module.read_text(encoding="utf-8"), "value = 1\n")
        self.assertFalse((self.test_root / "new.py").exists())

    def test_forced_limit_failure_returns_nonzero_and_failed_state(self) -> None:
        self.write_skill("fix")
        paths = WorkspacePaths.create(self.test_root).ensure()
        state = CodingTaskState.create(
            "Issue", "repo", task_id="limit-task", maximum_iterations=1
        )
        state.current_iteration = 1
        JsonTaskStore(paths).save(state)
        code, payload, error = self.run_cli(
            "transition",
            "--task-id",
            "limit-task",
            "--to",
            "ANALYZING",
            "--reason",
            "attempt beyond limit",
        )
        self.assertEqual((code, error), (2, ""))
        self.assertEqual(payload["current_status"], "FAILED")

    def test_request_approval_and_approve_commands_preserve_resume_target(self) -> None:
        self.write_skill("fix")
        self.write_skill("project-management")
        paths = WorkspacePaths.create(self.test_root).ensure()
        state = CodingTaskState.create("Issue", "repo", task_id="approval-task")
        state.current_status = WorkflowStatus.PLANNING
        state.current_iteration = 3
        state.implementation_plan = ImplementationPlan(
            "Implement",
            [ImplementationStep("s1", "modify", "src/app.py", "Implement", [])],
        )
        JsonTaskStore(paths).save(state)

        code, waiting, error = self.run_cli(
            "request-approval",
            "--task-id",
            "approval-task",
            "--resume-to",
            "EDITING",
            "--reason",
            "approve edit",
        )
        self.assertEqual((code, error), (0, ""))
        self.assertEqual(waiting["current_status"], "WAITING_APPROVAL")
        self.assertEqual(waiting["approval_return_status"], "EDITING")

        code, approved, error = self.run_cli(
            "approve", "--task-id", "approval-task", "--reason", "approved"
        )
        self.assertEqual((code, error), (0, ""))
        self.assertEqual(approved["current_status"], "EDITING")
        self.assertIsNone(approved["approval_return_status"])

    def test_report_command_emits_only_verified_final_report(self) -> None:
        paths = WorkspacePaths.create(self.test_root).ensure()
        state = CodingTaskState.create("Issue", "repo", task_id="report-cli")
        state.current_status = WorkflowStatus.COMPLETED
        state.acceptance_criteria = ["Tests pass"]
        state.retrieved_evidence = [
            RepositoryEvidence("c1", "src/app.py", 1, 2, "code", 1.0, "exact")
        ]
        state.implementation_plan = ImplementationPlan(
            "Implement",
            [ImplementationStep("s1", "modify", "src/app.py", "Implement", [])],
        )
        state.current_plan_step_index = 1
        state.completed_plan_step_ids = ["s1"]
        state.modified_files = ["src/app.py"]
        state.test_results = [
            TestExecution(["python"], "unit", 0, 1, 0, 4, "ok", "")
        ]
        state.final_summary = "Implemented safely."
        state.final_diff = "diff --git a/src/app.py b/src/app.py"
        state.pr_summary = "Implemented safely."
        state.final_citations = ["src/app.py:1-2"]
        state.final_report = FinalReport(
            "completed",
            state.final_summary,
            "Repository evidence supports the patch.",
            ["src/app.py: Implement"],
            ["unit: PASS (1 passed, 0 failed, 4 ms)"],
            ["Approved: no blocking findings."],
            state.final_citations,
            ["No known limitations."],
        )
        JsonTaskStore(paths).save(state)

        code, payload, error = self.run_cli("report", "--task-id", "report-cli")
        self.assertEqual((code, error), (0, ""))
        self.assertEqual(payload["status"], "completed")
        self.assertEqual(payload["evidence"], ["src/app.py:1-2"])
        self.assertNotIn("final_diff", payload)


if __name__ == "__main__":
    unittest.main()
