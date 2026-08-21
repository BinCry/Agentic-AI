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
