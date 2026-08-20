"""Bounded context projection and compaction for durable workflow turns."""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

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
        working["evidence"] = evidence[-4:]
        working["recent_errors"] = list(working.get("recent_errors", []))[-2:]
        working["recent_tools"] = list(working.get("recent_tools", []))[-3:]
        content = self._encode(working)
        if len(content) <= self.maximum_chars:
            return content
        prefix = content[: max(1, self.maximum_chars - 64)]
        compacted = self._encode({"truncated": True, "context_prefix": prefix})
        while len(compacted) > self.maximum_chars and prefix:
            prefix = prefix[: max(1, len(prefix) - 256)]
            compacted = self._encode({"truncated": True, "context_prefix": prefix})
        return compacted

    @staticmethod
    def _encode(payload: dict[str, Any]) -> str:
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


class ContextProjector:
    """Project state into bounded, decision-relevant fields without raw history."""

    def __init__(self, compactor: ContextCompactor | None = None) -> None:
        self.compactor = compactor or ContextCompactor()

    def project(self, state: CodingTaskState, decision_name: str) -> str:
        payload: dict[str, Any] = {
            "decision": decision_name,
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
                    "content": item.content[:6_000],
                }
                for item in state.retrieved_evidence[-8:]
            ],
            "plan": asdict(state.implementation_plan) if state.implementation_plan else None,
            "modified_files": state.modified_files,
            "recent_errors": [asdict(item) for item in state.errors[-4:]],
            "recent_tools": [asdict(item) for item in state.tool_execution_trace[-6:]],
            "limits": {
                "iteration": [state.current_iteration, state.maximum_iterations],
                "repair": [state.current_repair_iteration, state.maximum_repair_iterations],
                "retrieval_retry": [state.retrieval_retry_count, state.maximum_retrieval_retries],
            },
        }
        return self.compactor.compact(payload)
