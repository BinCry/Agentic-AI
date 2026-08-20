from __future__ import annotations

import json
import unittest
from contextlib import redirect_stdout
from io import StringIO

from coding_agent.cli import main
from coding_agent.evaluation.runner import BenchmarkSchemaError, EvaluationRunner
from coding_agent.models.records import TestExecution, ToolTraceRecord
from coding_agent.models.task_state import CodingTaskState
from coding_agent.storage.workspace import WorkspacePaths

from tests.support import WorkspaceTestCase


class EvaluationTests(WorkspaceTestCase):
    def test_runner_emits_honest_machine_readable_metrics(self) -> None:
        source = self.test_root / "module.py"
        source.write_text("def needle():\n    return 'value'\n", encoding="utf-8")
        benchmark = self.test_root / "benchmark.json"
        benchmark.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "name": "fixture",
                    "cases": [
                        {
                            "case_id": "needle",
                            "query": "needle",
                            "issue": "Find the needle implementation",
                            "relevant_paths": ["module.py"],
                            "expected_files": ["module.py"],
                            "acceptance_criteria": ["The needle function remains callable"],
                            "expected_tests": ["python -m unittest"],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

        report = EvaluationRunner(WorkspacePaths.create(self.test_root).ensure()).run(benchmark)
        self.assertEqual(report["schema_version"], 1)
        retrieval = report["retrieval"]
        self.assertEqual(retrieval["case_count"], 1)
        self.assertEqual(retrieval["recall_at_k"], 1.0)
        self.assertEqual(retrieval["mrr"], 1.0)
        self.assertEqual(retrieval["citation_correctness"], 1.0)
        self.assertEqual(report["coding_agent"]["sample_count"], 0)
        self.assertIsNone(report["coding_agent"]["completion_rate"])

    def test_schema_rejects_duplicate_case_ids(self) -> None:
        benchmark = self.test_root / "invalid.json"
        benchmark.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "name": "invalid",
                    "cases": [
                        {"case_id": "same", "query": "a", "relevant_paths": ["a.py"]},
                        {"case_id": "same", "query": "b", "relevant_paths": ["b.py"]},
                    ],
                }
            ),
            encoding="utf-8",
        )
        with self.assertRaises(BenchmarkSchemaError):
            EvaluationRunner(WorkspacePaths.create(self.test_root).ensure()).run(benchmark)

    def test_cli_evaluate_emits_json_report(self) -> None:
        (self.test_root / "module.py").write_text("def needle():\n    return 1\n", encoding="utf-8")
        benchmark = self.test_root / "benchmark.json"
        benchmark.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "name": "cli-fixture",
                    "cases": [
                        {
                            "case_id": "needle",
                            "query": "needle",
                            "issue": "Find the needle implementation",
                            "relevant_paths": ["module.py"],
                            "expected_files": ["module.py"],
                            "acceptance_criteria": ["The needle function remains callable"],
                            "expected_tests": ["python -m unittest"],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        output = StringIO()
        with redirect_stdout(output):
            code = main(
                [
                    "--workspace",
                    str(self.test_root),
                    "evaluate",
                    "--benchmark",
                    "benchmark.json",
                    "--top-k",
                    "1",
                ]
            )
        self.assertEqual(code, 0)
        report = json.loads(output.getvalue())
        self.assertEqual(report["retrieval"]["recall_at_k"], 1.0)

    def test_task_metrics_include_resolution_repair_test_and_invalid_call_rates(self) -> None:
        (self.test_root / "module.py").write_text("def needle():\n    return 1\n", encoding="utf-8")
        benchmark = self.test_root / "benchmark.json"
        benchmark.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "name": "metrics-fixture",
                    "cases": [
                        {
                            "case_id": "needle",
                            "query": "needle",
                            "issue": "Validate metrics",
                            "relevant_paths": ["module.py"],
                            "expected_files": ["module.py"],
                            "acceptance_criteria": ["The function remains callable"],
                            "expected_tests": [],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        state = CodingTaskState.create("Validate metrics", "fixture", task_id="metrics-task")
        state.current_repair_iteration = 2
        state.test_results.append(TestExecution(["python"], "unit", 0, 1, 0, 2, "", ""))
        state.tool_execution_trace.append(
            ToolTraceRecord(
                event_id="trace-1",
                timestamp="2026-01-01T00:00:00+00:00",
                workflow_state="TESTING",
                skill=None,
                tool="repo.read_file",
                success=False,
                latency_ms=1,
                result_metadata={"error_code": "TOOL_REQUEST_INVALID"},
                error="invalid request",
            )
        )
        report = EvaluationRunner(WorkspacePaths.create(self.test_root).ensure()).run(
            benchmark, states=[state]
        )
        metrics = report["coding_agent"]
        self.assertEqual(metrics["issue_resolution_rate"], 0.0)
        self.assertEqual(metrics["average_repair_attempts"], 2.0)
        self.assertEqual(metrics["test_pass_rate"], 1.0)
        self.assertEqual(metrics["invalid_tool_call_rate"], 1.0)


if __name__ == "__main__":
    unittest.main()
