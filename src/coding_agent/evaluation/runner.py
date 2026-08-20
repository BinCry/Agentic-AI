"""Machine-readable retrieval and coding-agent evaluation without fabricated data."""

from __future__ import annotations

import json
import statistics
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable

from ..models.task_state import CodingTaskState
from ..rag.index import RepositoryIndex
from ..storage.workspace import WorkspacePaths


class BenchmarkSchemaError(ValueError):
    """Raised when a benchmark fixture does not match the supported schema."""


@dataclass(slots=True, frozen=True)
class RetrievalBenchmarkCase:
    case_id: str
    query: str
    relevant_paths: tuple[str, ...]

    @classmethod
    def from_dict(cls, payload: object) -> "RetrievalBenchmarkCase":
        if not isinstance(payload, dict):
            raise BenchmarkSchemaError("benchmark case must be an object")
        case_id = payload.get("case_id")
        query = payload.get("query")
        relevant = payload.get("relevant_paths")
        if (
            not isinstance(case_id, str)
            or not case_id.strip()
            or not isinstance(query, str)
            or not query.strip()
            or not isinstance(relevant, list)
            or not relevant
            or any(not isinstance(item, str) or not item.strip() for item in relevant)
        ):
            raise BenchmarkSchemaError(
                "case requires non-empty case_id, query and relevant_paths"
            )
        return cls(case_id.strip(), query.strip(), tuple(item.strip() for item in relevant))


@dataclass(slots=True, frozen=True)
class BenchmarkSuite:
    name: str
    schema_version: int
    cases: tuple[RetrievalBenchmarkCase, ...]

    @classmethod
    def from_file(cls, path: Path) -> "BenchmarkSuite":
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if not isinstance(payload, dict):
            raise BenchmarkSchemaError("benchmark suite must be an object")
        version = payload.get("schema_version")
        name = payload.get("name")
        raw_cases = payload.get("cases")
        if version != 1 or not isinstance(name, str) or not name.strip():
            raise BenchmarkSchemaError("benchmark suite requires schema_version 1 and name")
        if not isinstance(raw_cases, list) or not raw_cases:
            raise BenchmarkSchemaError("benchmark suite requires at least one case")
        cases = tuple(RetrievalBenchmarkCase.from_dict(item) for item in raw_cases)
        ids = [item.case_id for item in cases]
        if len(ids) != len(set(ids)):
            raise BenchmarkSchemaError("benchmark case_id values must be unique")
        return cls(name.strip(), version, cases)


class EvaluationRunner:
    """Run retrieval and optional task-state metrics against real local data."""

    def __init__(self, paths: WorkspacePaths) -> None:
        self.paths = paths.ensure()

    def run(
        self,
        benchmark_path: str | Path,
        *,
        top_k: int = 5,
        states: Iterable[CodingTaskState] = (),
    ) -> dict[str, object]:
        if top_k < 1 or top_k > 100:
            raise ValueError("top_k must be between 1 and 100")
        suite_path = self.paths.resolve_workspace_path(benchmark_path, must_exist=True)
        suite = BenchmarkSuite.from_file(suite_path)
        index = RepositoryIndex(self.paths)
        cases: list[dict[str, object]] = []
        latencies: list[int] = []
        for case in suite.cases:
            result = index.retrieve_grounded_with_metrics(case.query, top_k=top_k)
            paths = [_canonical_path(self.paths, hit.evidence.path) for hit in result.hits]
            relevant = {_canonical_path(self.paths, path) for path in case.relevant_paths}
            first_rank = next(
                (rank for rank, path in enumerate(paths, start=1) if path in relevant), None
            )
            grounded = sum(1 for hit in result.hits if index.verify_evidence(hit.evidence))
            latencies.append(result.metrics.latency_ms)
            cases.append(
                {
                    "case_id": case.case_id,
                    "query": case.query,
                    "retrieved_paths": paths,
                    "relevant_paths": sorted(relevant),
                    "recall_at_k": len(set(paths) & relevant) / len(relevant),
                    "mrr": 1.0 / first_rank if first_rank else 0.0,
                    "citation_correctness": grounded / len(result.hits) if result.hits else None,
                    "latency_ms": result.metrics.latency_ms,
                    "failure": None
                    if first_rank and grounded == len(result.hits)
                    else {
                        "missing_relevant": sorted(relevant - set(paths)),
                        "ungrounded_hits": len(result.hits) - grounded,
                    },
                }
            )
        task_states = list(states)
        return {
            "schema_version": 1,
            "benchmark": {
                "name": suite.name,
                "path": str(suite_path.relative_to(self.paths.workspace_root)),
            },
            "generated_at": datetime.now(UTC).isoformat(),
            "retrieval": {
                "case_count": len(cases),
                "top_k": top_k,
                "recall_at_k": _average(item["recall_at_k"] for item in cases),
                "mrr": _average(item["mrr"] for item in cases),
                "citation_correctness": _average_optional(
                    item["citation_correctness"] for item in cases
                ),
                "latency_ms": _latency_metrics(latencies),
            },
            "coding_agent": _task_metrics(task_states, index),
            "cases": cases,
        }


def _average(values: Iterable[object]) -> float | None:
    numbers = [float(value) for value in values if isinstance(value, (int, float))]
    return statistics.fmean(numbers) if numbers else None


def _canonical_path(paths: WorkspacePaths, value: str) -> str:
    resolved = paths.resolve_workspace_path(value, must_exist=True)
    return resolved.relative_to(paths.workspace_root).as_posix()


def _average_optional(values: Iterable[object]) -> float | None:
    return _average(value for value in values if value is not None)


def _latency_metrics(values: list[int]) -> dict[str, int | None]:
    if not values:
        return {"mean": None, "p95": None, "max": None}
    ordered = sorted(values)
    p95_index = min(len(ordered) - 1, max(0, int(len(ordered) * 0.95) - 1))
    return {
        "mean": int(statistics.fmean(ordered)),
        "p95": ordered[p95_index],
        "max": max(ordered),
    }


def _task_metrics(states: list[CodingTaskState], index: RepositoryIndex) -> dict[str, object]:
    if not states:
        return {
            "sample_count": 0,
            "completion_rate": None,
            "repair_rate": None,
            "regression_pass_rate": None,
            "tool_failure_rate": None,
            "citation_correctness": None,
            "failure_analysis": [],
        }
    completed = sum(state.current_status.value == "COMPLETED" for state in states)
    repaired = sum(state.current_repair_iteration > 0 for state in states)
    unit_states = [
        state for state in states if any(item.target == "unit" for item in state.test_results)
    ]
    unit_passed = sum(
        any(
            item.target == "unit"
            and item.exit_code == 0
            and item.failed_count == 0
            and not item.timed_out
            for item in state.test_results
        )
        for state in unit_states
    )
    traces = [trace for state in states for trace in state.tool_execution_trace]
    evidence = [item for state in states for item in state.retrieved_evidence]
    failures = [
        {
            "task_id": state.task_id,
            "status": state.current_status.value,
            "errors": [asdict(item) for item in state.errors],
        }
        for state in states
        if state.current_status.value != "COMPLETED" or state.errors
    ]
    return {
        "sample_count": len(states),
        "completion_rate": completed / len(states),
        "repair_rate": repaired / len(states),
        "regression_pass_rate": unit_passed / len(unit_states) if unit_states else None,
        "tool_failure_rate": (
            sum(not trace.success for trace in traces) / len(traces) if traces else None
        ),
        "citation_correctness": (
            sum(index.verify_evidence(item) for item in evidence) / len(evidence)
            if evidence
            else None
        ),
        "failure_analysis": failures,
    }
