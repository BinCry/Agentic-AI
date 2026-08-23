from __future__ import annotations

import json
import io
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from coding_agent.cli import main
from coding_agent.evaluation.baseline import BaselineRunner
from coding_agent.storage.workspace import WorkspacePaths
from coding_agent.tools.process import BoundedProcessResult

from tests.support import WorkspaceTestCase


class ScriptedCommandRunner:
    def __init__(self, *, coverage_available: bool = False, unit_exit_code: int = 0) -> None:
        self.coverage_available = coverage_available
        self.unit_exit_code = unit_exit_code
        self.environments: list[dict[str, str]] = []

    def __call__(
        self,
        command: list[str],
        *,
        cwd: Path,
        timeout_seconds: float,
        maximum_output_bytes: int,
        environment: dict[str, str],
    ) -> BoundedProcessResult:
        del cwd, timeout_seconds, maximum_output_bytes
        self.environments.append(dict(environment))
        text = " ".join(command)
        if "coverage run" in text and not self.coverage_available:
            return self.result(command, 1, stderr="No module named coverage")
        if "coverage json" in text:
            output = Path(command[command.index("-o") + 1])
            output.write_text(
                json.dumps(
                    {
                        "totals": {
                            "percent_covered": 82.5,
                            "num_statements": 100,
                            "covered_lines": 85,
                            "num_branches": 20,
                            "covered_branches": 15,
                        }
                    }
                ),
                encoding="utf-8",
            )
            return self.result(command, 0)
        if "pip wheel" in text:
            wheel_dir = Path(command[command.index("--wheel-dir") + 1])
            wheel_dir.mkdir(parents=True, exist_ok=True)
            (wheel_dir / "agentic_coding_agent-0.1.0-py3-none-any.whl").write_bytes(b"wheel")
            return self.result(command, 0)
        if "unittest discover" in text:
            return self.result(
                command,
                self.unit_exit_code,
                stderr="Ran 12 tests in 0.100s\n\nOK\n" if self.unit_exit_code == 0 else "FAILED",
            )
        return self.result(command, 0, stdout="0.1.0\n")

    @staticmethod
    def result(
        command: list[str], exit_code: int, *, stdout: str = "", stderr: str = ""
    ) -> BoundedProcessResult:
        return BoundedProcessResult(
            tuple(command), exit_code, stdout, stderr, False, False, False
        )


class BaselineRunnerTests(WorkspaceTestCase):
    def write_benchmark(self) -> Path:
        (self.test_root / "pyproject.toml").write_text(
            "[build-system]\nrequires = []\nbuild-backend = 'fixture'\n",
            encoding="utf-8",
        )
        (self.test_root / "README.md").write_text("# Fixture\n", encoding="utf-8")
        (self.test_root / "src").mkdir()
        (self.test_root / "module.py").write_text(
            "def needle():\n    return 1\n", encoding="utf-8"
        )
        benchmark = self.test_root / "benchmark.json"
        benchmark.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "name": "baseline-fixture",
                    "cases": [
                        {
                            "case_id": "needle",
                            "query": "needle",
                            "issue": "Find the needle",
                            "relevant_paths": ["module.py"],
                            "expected_files": ["module.py"],
                            "acceptance_criteria": ["Needle remains callable"],
                            "expected_tests": [],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        return benchmark

    def test_report_marks_optional_coverage_unavailable_without_false_pass(self) -> None:
        benchmark = self.write_benchmark()
        paths = WorkspacePaths.create(self.test_root).ensure()
        output = Path("reports/baseline.json")

        command_runner = ScriptedCommandRunner()
        report = BaselineRunner(paths, command_runner=command_runner).run(
            benchmark, output_path=output
        )

        self.assertEqual(report["schema_version"], 1)
        self.assertEqual(report["status"], "passed")
        self.assertEqual(report["gates"]["unit_tests"]["test_count"], 12)
        self.assertEqual(report["gates"]["branch_coverage"]["status"], "unavailable")
        self.assertFalse(report["gates"]["branch_coverage"]["required"])
        self.assertEqual(report["evaluation"]["retrieval"]["recall_at_k"], 1.0)
        self.assertEqual(
            json.loads((self.test_root / output).read_text(encoding="utf-8")), report
        )
        self.assertTrue(
            all(item["PIP_NO_INDEX"] == "1" for item in command_runner.environments)
        )

    def test_required_unavailable_coverage_and_failed_units_fail_baseline(self) -> None:
        benchmark = self.write_benchmark()
        paths = WorkspacePaths.create(self.test_root).ensure()
        coverage_report = BaselineRunner(
            paths, command_runner=ScriptedCommandRunner()
        ).run(benchmark, require_coverage=True)
        unit_report = BaselineRunner(
            paths, command_runner=ScriptedCommandRunner(unit_exit_code=1)
        ).run(benchmark)

        self.assertEqual(coverage_report["status"], "failed")
        self.assertTrue(coverage_report["gates"]["branch_coverage"]["required"])
        self.assertEqual(unit_report["status"], "failed")
        self.assertEqual(unit_report["gates"]["unit_tests"]["status"], "failed")

    def test_available_coverage_reports_branch_metrics(self) -> None:
        benchmark = self.write_benchmark()
        paths = WorkspacePaths.create(self.test_root).ensure()

        report = BaselineRunner(
            paths, command_runner=ScriptedCommandRunner(coverage_available=True)
        ).run(benchmark, require_coverage=True)

        gate = report["gates"]["branch_coverage"]
        self.assertEqual(gate["status"], "passed")
        self.assertEqual(gate["percent_covered"], 82.5)
        self.assertEqual(gate["branches"], 20)

    def test_invalid_coverage_threshold_fails_with_bounded_diagnostic(self) -> None:
        benchmark = self.write_benchmark()
        pyproject = self.test_root / "pyproject.toml"
        pyproject.write_text(
            pyproject.read_text(encoding="utf-8")
            + "\n[tool.coverage.report]\nfail_under = 'invalid'\n",
            encoding="utf-8",
        )
        paths = WorkspacePaths.create(self.test_root).ensure()

        report = BaselineRunner(
            paths, command_runner=ScriptedCommandRunner(coverage_available=True)
        ).run(benchmark, require_coverage=True)

        gate = report["gates"]["branch_coverage"]
        self.assertEqual(report["status"], "failed")
        self.assertEqual(gate["status"], "failed")
        self.assertEqual(gate["diagnostic"], "coverage configuration is invalid")

    def test_cli_returns_nonzero_for_failed_required_gate(self) -> None:
        report = {"schema_version": 1, "status": "failed"}
        output = io.StringIO()
        with patch("coding_agent.cli_baseline.BaselineRunner") as runner_type:
            runner_type.return_value.run.return_value = report
            with redirect_stdout(output):
                code = main(
                    [
                        "--workspace",
                        str(self.test_root),
                        "baseline",
                        "--output",
                        "reports/baseline.json",
                        "--require-coverage",
                    ]
                )

        self.assertEqual(code, 2)
        self.assertEqual(json.loads(output.getvalue()), report)
        runner_type.return_value.run.assert_called_once()

    def test_output_symlink_is_rejected_before_creating_artifacts(self) -> None:
        benchmark = self.write_benchmark()
        paths = WorkspacePaths.create(self.test_root).ensure()
        victim = self.test_root / "victim.json"
        victim.write_text("preserve", encoding="utf-8")
        output = self.test_root / "baseline-link.json"
        try:
            output.symlink_to(victim)
        except OSError as exc:
            self.skipTest(f"file symlinks unavailable: {exc}")

        with self.assertRaisesRegex(ValueError, "symbolic link"):
            BaselineRunner(paths, command_runner=ScriptedCommandRunner()).run(
                benchmark, output_path="baseline-link.json"
            )

        self.assertEqual(victim.read_text(encoding="utf-8"), "preserve")
        self.assertFalse(paths.resolve_runtime_path("baselines").exists())


if __name__ == "__main__":
    unittest.main()
