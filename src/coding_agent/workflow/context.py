"""Bounded context projection and compaction for durable workflow turns."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from ..models.decision_schemas import decision_output_schema
from ..models.records import RepositoryEvidence
from ..models.task_state import CodingTaskState
from ..storage.observation_store import ObservationStore
from .context_budget import ContextBudget, ContextBudgeter, ContextSection


class ContextCompactor:
    """Compatibility wrapper over priority-based context budgeting."""

    def __init__(self, maximum_chars: int = 24_000) -> None:
        if maximum_chars < 1_000:
            raise ValueError("maximum context must be at least 1000 characters")
        self.maximum_chars = maximum_chars
        self.budgeter = ContextBudgeter()
        self.budget = ContextBudget(
            maximum_tokens=max(1, maximum_chars // 3),
            maximum_chars=maximum_chars,
        )

    def compact(self, payload: dict[str, Any]) -> str:
        if not isinstance(payload, dict):
            raise TypeError("context payload must be an object")
        sections = [
            ContextSection(
                key,
                value,
                self._priority(key),
                required=key in self._required_keys(),
                fallback=self._fallback(key, value),
            )
            for key, value in payload.items()
            if key != "truncated"
        ]
        return self.budgeter.project(sections, self.budget).to_json()

    @staticmethod
    def _priority(key: str) -> int:
        return {
            "decision": 110,
            "output_schema": 109,
            "workflow_mode": 105,
            "task_id": 104,
            "issue": 103,
            "problem": 102,
            "status": 101,
            "acceptance_criteria": 100,
            "limits": 99,
            "active_skill": 96,
            "project": 95,
            "evidence": 90,
            "retrieval_queries": 85,
            "plan": 80,
            "plan_progress": 79,
            "debug": 78,
            "modified_files": 77,
            "observations": 70,
            "output_requirements": 108,
            "recent_tests": 40,
            "recent_errors": 30,
            "recent_tools": 20,
        }.get(key, 10)

    @staticmethod
    def _required_keys() -> frozenset[str]:
        return frozenset(
            {
                "decision",
                "output_schema",
                "workflow_mode",
                "task_id",
                "issue",
                "status",
                "evidence",
            }
        )

    @staticmethod
    def _fallback(key: str, value: Any) -> Any:
        if key == "issue" and isinstance(value, str):
            return value[:1_000]
        if key == "evidence" and isinstance(value, list):
            provenance_fields = (
                "chunk_id",
                "path",
                "lines",
                "digest",
                "score",
                "retrieval_method",
            )
            return [
                {name: item.get(name) for name in provenance_fields}
                for item in value
                if isinstance(item, dict)
            ]
        if key == "project" and isinstance(value, dict):
            instructions = []
            for item in value.get("instructions", []):
                if isinstance(item, dict):
                    instructions.append(
                        {
                            **item,
                            "content": str(item.get("content", ""))[:500],
                            "truncated": True,
                        }
                    )
            return {
                "workspace_name": value.get("workspace_name"),
                "ecosystems": value.get("ecosystems", []),
                "instructions": instructions,
            }
        if key in {"recent_tests", "recent_errors", "recent_tools"} and isinstance(
            value, list
        ):
            return value[-1:]
        return None


class ContextProjector:
    """Project state into bounded, decision-relevant fields without raw history."""

    def __init__(
        self,
        compactor: ContextCompactor | None = None,
        observation_store: ObservationStore | None = None,
    ) -> None:
        self.compactor = compactor or ContextCompactor()
        self.observation_store = observation_store

    def project(self, state: CodingTaskState, decision_name: str) -> str:
        output_schema = decision_output_schema(decision_name)
        if decision_name == "IssueAnalysis":
            output_schema["properties"]["task_type"]["enum"] = (
                ["analysis"]
                if state.read_only
                else ["bug_fix", "feature", "refactor", "test"]
            )
        payload: dict[str, Any] = {
            "decision": decision_name,
            "output_schema": output_schema,
            "workflow_mode": "read_only" if state.read_only else "coding",
            "task_id": state.task_id,
            "issue": state.original_issue,
            "problem": state.normalized_problem_statement,
            "status": state.current_status.value,
            "active_skill": asdict(state.active_skill) if state.active_skill else None,
            "project": self._project_context(state),
            "acceptance_criteria": state.acceptance_criteria,
            "retrieval_queries": state.retrieval_queries[-8:],
            "evidence": [
                {
                    "chunk_id": item.chunk_id,
                    "path": item.path,
                    "lines": [item.start_line, item.end_line],
                    "digest": item.file_digest,
                    "score": item.score,
                    "retrieval_method": item.retrieval_method,
                    "content": item.content[:6_000],
                }
                for item in sorted(
                    state.retrieved_evidence,
                    key=lambda item: self._evidence_priority(state, item),
                )[:8]
            ],
            "plan": asdict(state.implementation_plan) if state.implementation_plan else None,
            "plan_progress": {
                "current_step_index": state.current_plan_step_index,
                "completed_step_ids": state.completed_plan_step_ids,
            },
            "debug": {
                "root_cause": state.debug_root_cause,
                "evidence": state.debug_evidence,
                "next_action": state.debug_action,
                "repair_pending": state.pending_repair,
            },
            "modified_files": state.modified_files,
            "recent_tests": [
                {
                    "command": item.command,
                    "target": item.target,
                    "exit_code": item.exit_code,
                    "passed_count": item.passed_count,
                    "failed_count": item.failed_count,
                    "duration_ms": item.duration_ms,
                    "stdout_summary": item.stdout_summary[-2_000:],
                    "stderr_summary": item.stderr_summary[-2_000:],
                    "timed_out": item.timed_out,
                }
                for item in state.test_results[-4:]
            ],
            "recent_errors": [asdict(item) for item in state.errors[-4:]],
            "recent_tools": [asdict(item) for item in state.tool_execution_trace[-6:]],
            "observations": self._observation_references(state),
            "limits": {
                "iteration": [state.current_iteration, state.maximum_iterations],
                "repair": [state.current_repair_iteration, state.maximum_repair_iterations],
                "retrieval_retry": [state.retrieval_retry_count, state.maximum_retrieval_retries],
            },
        }
        if decision_name == "TaskCompletionResult":
            payload["output_requirements"] = {
                "status": "completed or failed",
                "summary": "concise implemented outcome",
                "reasoning": "root cause for a bug or repository-grounded implementation reasoning",
                "modified_files": "exact paths modified by controlled tools",
                "tests_passed": "must agree with current test executions",
                "citations": "repository path and line citations",
                "unresolved_findings": "known non-blocking limitations; use an empty list when none",
                "pr_summary": "optional pull-request summary",
            }
        return self.compactor.compact(payload)

    def _observation_references(self, state: CodingTaskState) -> list[dict[str, Any]]:
        if self.observation_store is None:
            return []
        records = self.observation_store.list(state.task_id)[-8:]
        return [
            {
                "observation_id": item.observation_id,
                "tool": item.tool_name,
                "status": item.status,
                "summary": item.summary,
                "result_sha256": item.result_sha256,
                "artifact_path": item.artifact_path,
                "result_bytes": item.result_bytes,
                "truncated": item.truncated,
            }
            for item in records
        ]

    @staticmethod
    def _evidence_priority(
        state: CodingTaskState, item: RepositoryEvidence
    ) -> tuple[bool, float, str, int, str]:
        citations = list(state.final_citations)
        citations.extend(state.debug_evidence)
        if state.implementation_plan is not None:
            citations.extend(state.implementation_plan.evidence_citations)
        cited = any(
            citation.replace("\\", "/").startswith(f"{item.path}:")
            for citation in citations
        )
        return (not cited, -item.score, item.path, item.start_line, item.chunk_id)

    @staticmethod
    def _project_context(state: CodingTaskState) -> dict[str, Any] | None:
        profile = state.project_profile
        if profile is None:
            return None
        return {
            "schema_version": profile.schema_version,
            "workspace_name": profile.workspace_name,
            "ecosystems": list(profile.ecosystems),
            "package_managers": list(profile.package_managers),
            "manifests": [item.to_dict() for item in profile.manifests],
            "candidate_commands": [item.to_dict() for item in profile.commands],
            "instructions": [
                {
                    "path": item.path,
                    "scope": item.scope,
                    "sha256": item.sha256,
                    "content": item.content[:2_000],
                    "truncated": item.truncated or len(item.content) > 2_000,
                    "trust": "untrusted_repository_data",
                }
                for item in profile.instructions[:4]
            ],
        }
