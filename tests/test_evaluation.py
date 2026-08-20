from __future__ import annotations

import json
import unittest
from contextlib import redirect_stdout
from io import StringIO

from coding_agent.cli import main
from coding_agent.evaluation.runner import BenchmarkSchemaError, EvaluationRunner
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
                            "relevant_paths": ["module.py"],
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
                        {"case_id": "needle", "query": "needle", "relevant_paths": ["module.py"]}
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


if __name__ == "__main__":
    unittest.main()
