"""Process, runtime, and coverage gates for the local capability baseline."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import sys
import time
import tomllib
from pathlib import Path
from typing import Any, Callable

from ..storage.workspace import WorkspacePaths
from ..tools.process import BoundedProcessResult, safe_environment
from .baseline_wheel import run_wheel_gate


CommandRunner = Callable[..., BoundedProcessResult]
TEST_COUNT_RE = re.compile(r"Ran\s+(\d+)\s+tests?")


class BaselineGateRunner:
    def __init__(
        self, paths: WorkspacePaths, run_root: Path, command_runner: CommandRunner
    ) -> None:
        self.paths = paths
        self.run_root = run_root
        self.command_runner = command_runner
        self.environment = self._environment()

    def run(self, *, require_coverage: bool) -> dict[str, dict[str, Any]]:
        return {
            "runtime_paths": self._runtime_gate(),
            "unit_tests": self._unit_gate(),
            "read_only_workflow": self._read_only_gate(),
            "branch_coverage": self._coverage_gate(required=require_coverage),
            "wheel_smoke": run_wheel_gate(
                self.paths, self.run_root, self.environment, self.command_gate
            ),
        }

    def _environment(self) -> dict[str, str]:
        environment = safe_environment(self.paths.workspace_root, self.paths.runtime_root)
        environment["CODING_AGENT_TEST_TMP"] = str(self.run_root / "test-temp")
        environment["COVERAGE_FILE"] = str(self.run_root / ".coverage")
        environment["PIP_CACHE_DIR"] = str(self.run_root / "pip-cache")
        environment["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
        environment["PIP_NO_INDEX"] = "1"
        module_roots: list[str] = []
        for module_name in ("coverage", "setuptools", "wheel"):
            module_spec = importlib.util.find_spec(module_name)
            if module_spec and module_spec.origin:
                module_roots.append(str(Path(module_spec.origin).resolve().parent.parent))
        environment["PYTHONPATH"] = os.pathsep.join(
            [environment["PYTHONPATH"], *dict.fromkeys(module_roots)]
        )
        return environment

    def _runtime_gate(self) -> dict[str, Any]:
        writable = [
            self.paths.runtime_root,
            self.paths.runtime_root / "process-temp",
            self.paths.runtime_root / "process-home",
            self.run_root,
            self.run_root / "test-temp",
            self.run_root / "pip-cache",
        ]
        forbidden = [
            str(path)
            for path in writable
            if path.drive.upper() in self.paths.forbidden_drives
        ]
        return {
            "status": "failed" if forbidden else "passed",
            "required": True,
            "workspace_root": str(self.paths.workspace_root),
            "runtime_root": str(self.paths.runtime_root),
            "forbidden_writable_paths": forbidden,
        }

    def _unit_gate(self) -> dict[str, Any]:
        gate = self.command_gate(
            [sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests"],
            required=True,
            timeout_seconds=120,
        )
        output = f"{gate.pop('_stdout', '')}\n{gate.pop('_stderr', '')}"
        match = TEST_COUNT_RE.search(output)
        gate["test_count"] = int(match.group(1)) if match else None
        if gate["status"] == "passed" and match is None:
            gate["status"] = "failed"
            gate["diagnostic"] = "unit test output did not report a test count"
        return gate

    def _read_only_gate(self) -> dict[str, Any]:
        gate = self.command_gate(
            [
                sys.executable,
                "-B",
                "-m",
                "unittest",
                "tests.test_workflow_runtime.WorkflowRuntimeTests."
                "test_read_only_analysis_completes_without_mutation_or_tests",
            ],
            required=True,
            timeout_seconds=60,
        )
        gate.pop("_stdout", None)
        gate.pop("_stderr", None)
        return gate

    def _coverage_gate(self, *, required: bool) -> dict[str, Any]:
        run_gate = self.command_gate(
            [
                sys.executable,
                "-B",
                "-m",
                "coverage",
                "run",
                "--branch",
                "-m",
                "unittest",
                "discover",
                "-s",
                "tests",
            ],
            required=required,
            timeout_seconds=180,
        )
        diagnostics = f"{run_gate.pop('_stdout', '')}\n{run_gate.pop('_stderr', '')}"
        if run_gate["status"] != "passed":
            if "No module named coverage" in diagnostics:
                run_gate["status"] = "unavailable"
                run_gate["diagnostic"] = "install the test extra to collect branch coverage"
            return run_gate
        output = self.run_root / "coverage.json"
        json_gate = self.command_gate(
            [sys.executable, "-B", "-m", "coverage", "json", "-o", str(output)],
            required=required,
            timeout_seconds=30,
        )
        json_gate.pop("_stdout", None)
        json_gate.pop("_stderr", None)
        if json_gate["status"] != "passed" or not output.is_file():
            return json_gate
        try:
            totals = json.loads(output.read_text(encoding="utf-8"))["totals"]
            json_gate.update(
                percent_covered=totals["percent_covered"],
                statements=totals["num_statements"],
                covered_lines=totals["covered_lines"],
                branches=totals["num_branches"],
                covered_branches=totals["covered_branches"],
            )
        except (KeyError, TypeError, ValueError, OSError):
            json_gate["status"] = "failed"
            json_gate["diagnostic"] = "coverage JSON is invalid"
            return json_gate
        try:
            threshold = self._coverage_threshold()
        except (TypeError, ValueError, OSError, tomllib.TOMLDecodeError):
            json_gate["status"] = "failed"
            json_gate["diagnostic"] = "coverage configuration is invalid"
            return json_gate
        json_gate["minimum_percent"] = threshold
        if totals["percent_covered"] < threshold:
            json_gate["status"] = "failed"
            json_gate["diagnostic"] = "branch coverage is below the configured threshold"
        return json_gate

    def _coverage_threshold(self) -> float:
        pyproject = self.paths.resolve_workspace_path("pyproject.toml", must_exist=True)
        with pyproject.open("rb") as handle:
            payload = tomllib.load(handle)
        value = payload.get("tool", {}).get("coverage", {}).get("report", {}).get(
            "fail_under", 0
        )
        if not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0:
            raise ValueError("coverage fail_under must be a non-negative number")
        return float(value)

    def command_gate(
        self,
        command: list[str],
        *,
        required: bool,
        timeout_seconds: float,
        cwd: Path | None = None,
        environment: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        started = time.perf_counter()
        result = self.command_runner(
            command,
            cwd=cwd or self.paths.workspace_root,
            timeout_seconds=timeout_seconds,
            maximum_output_bytes=64_000,
            environment=environment or self.environment,
        )
        return {
            "status": "passed" if result.exit_code == 0 and not result.timed_out else "failed",
            "required": required,
            "exit_code": result.exit_code,
            "timed_out": result.timed_out,
            "duration_ms": int((time.perf_counter() - started) * 1000),
            "stdout_sha256": hashlib.sha256(result.stdout.encode()).hexdigest(),
            "stderr_sha256": hashlib.sha256(result.stderr.encode()).hexdigest(),
            "stdout_truncated": result.stdout_truncated,
            "stderr_truncated": result.stderr_truncated,
            "_stdout": result.stdout,
            "_stderr": result.stderr,
        }
