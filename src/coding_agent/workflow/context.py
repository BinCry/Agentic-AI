"""Bounded context projection and compaction for durable workflow turns."""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

from ..models.decision_schemas import decision_output_schema
from ..models.task_state import CodingTaskState


class ContextCompactor:
    """Keep decision context useful while enforcing a hard serialized bound."""

    def __init__(self, maximum_chars: int = 24_000) -> None:
        if maximum_chars < 1_000:
            raise ValueError("maximum context must be at least 1000 characters")
        self.maximum_chars = maximum_chars

    def compact(self, payload: dict[str, Any]) -> str:
        working = dict(payload)
        content = self._encode(working)
        if len(content) <= self.maximum_chars:
            return content
        evidence = list(working.get("evidence", []))
        for item in evidence:
            item["content"] = item.get("content", "")[:1_000]
        working["evidence"] = evidence[:4]
        working["recent_errors"] = list(working.get("recent_errors", []))[-2:]
        working["recent_tools"] = list(working.get("recent_tools", []))[-3:]
        working["recent_tests"] = list(working.get("recent_tests", []))[-2:]
        content = self._encode(working)
        if len(content) <= self.maximum_chars:
            return content
        preserved = {
            key: working[key]
            for key in ("decision", "output_schema")
            if key in working
        }
        remainder = {key: value for key, value in working.items() if key not in preserved}
        prefix = self._encode(remainder)
        compacted = self._encode(
            {**preserved, "truncated": True, "context_prefix": prefix}
        )
        if len(self._encode({**preserved, "truncated": True, "context_prefix": ""})) > self.maximum_chars:
            prefix = content[: max(1, self.maximum_chars - 64)]
            compacted = self._encode({"truncated": True, "context_prefix": prefix})
        while len(compacted) > self.maximum_chars and prefix:
            prefix = prefix[: max(1, len(prefix) - 256)]
            compacted_payload = (
                {**preserved, "truncated": True, "context_prefix": prefix}
                if preserved and len(
                    self._encode({**preserved, "truncated": True, "context_prefix": ""})
                ) <= self.maximum_chars
                else {"truncated": True, "context_prefix": prefix}
            )
            compacted = self._encode(compacted_payload)
        return compacted

    @staticmethod
    def _encode(payload: dict[str, Any]) -> str:
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


class ContextProjector:
    """Project state into bounded, decision-relevant fields without raw history."""

    def __init__(self, compactor: ContextCompactor | None = None) -> None:
        self.compactor = compactor or ContextCompactor()

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
                    key=lambda item: (-item.score, item.path, item.start_line, item.chunk_id),
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
