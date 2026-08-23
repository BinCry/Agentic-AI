"""Reproducible local capability baseline with workspace-contained artifacts."""

from __future__ import annotations

import json
import os
import platform
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from .. import __version__
from ..models.task_state_schema import CURRENT_TASK_SCHEMA_VERSION
from ..storage.workspace import WorkspacePaths
from ..tools.process import run_bounded
from .baseline_gates import BaselineGateRunner, CommandRunner
from .runner import EvaluationRunner


class BaselineRunner:
    def __init__(
        self,
        paths: WorkspacePaths,
        *,
        command_runner: CommandRunner = run_bounded,
    ) -> None:
        self.paths = paths.ensure()
        self.command_runner = command_runner

    def run(
        self,
        benchmark_path: str | Path,
        *,
        top_k: int = 5,
        output_path: str | Path | None = None,
        require_coverage: bool = False,
    ) -> dict[str, Any]:
        target = self._output_path(output_path)
        run_root = self.paths.resolve_runtime_path(
            Path("baselines")
            / f"run-{datetime.now(UTC).strftime('%Y%m%dT%H%M%S')}-{uuid4().hex[:8]}"
        )
        run_root.mkdir(parents=True)
        gates = BaselineGateRunner(
            self.paths, run_root, self.command_runner
        ).run(require_coverage=require_coverage)
        evaluation: dict[str, Any] | None = None
        try:
            evaluation = EvaluationRunner(self.paths).run(benchmark_path, top_k=top_k)
            gates["retrieval_evaluation"] = {
                "status": "passed",
                "required": True,
                "recall_at_k": evaluation["retrieval"]["recall_at_k"],
                "citation_correctness": evaluation["retrieval"]["citation_correctness"],
            }
        except Exception as exc:
            gates["retrieval_evaluation"] = {
                "status": "failed",
                "required": True,
                "error": type(exc).__name__,
            }
        failed_required = [
            name
            for name, gate in gates.items()
            if gate["required"] and gate["status"] != "passed"
        ]
        report: dict[str, Any] = {
            "schema_version": 1,
            "status": "failed" if failed_required else "passed",
            "generated_at": datetime.now(UTC).isoformat(),
            "agent_version": __version__,
            "task_schema_version": CURRENT_TASK_SCHEMA_VERSION,
            "python_version": platform.python_version(),
            "platform": platform.system(),
            "artifact_root": run_root.relative_to(self.paths.workspace_root).as_posix(),
            "failed_required_gates": failed_required,
            "gates": gates,
            "evaluation": evaluation,
        }
        self._write_json_atomic(target, report)
        return report

    def _output_path(self, value: str | Path | None) -> Path:
        if value is None:
            candidate = self.paths.runtime_root / "baselines" / "latest.json"
            if candidate.is_symlink():
                raise ValueError("baseline output must not be a symbolic link")
            return self.paths.resolve_runtime_path("baselines/latest.json")
        candidate = Path(value)
        if candidate.is_absolute():
            raise ValueError("baseline output must be workspace-relative")
        unresolved = self.paths.workspace_root / candidate
        if unresolved.is_symlink():
            raise ValueError("baseline output must not be a symbolic link")
        return self.paths.resolve_workspace_path(candidate)

    @staticmethod
    def _write_json_atomic(target: Path, payload: dict[str, Any]) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(f".{target.name}.{os.getpid()}.{uuid4().hex}.tmp")
        try:
            with temporary.open("x", encoding="utf-8", newline="\n") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)
