"""Bounded one-action-at-a-time loop within durable workflow stages."""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Callable, Protocol

from ..errors import ErrorCode
from ..models.agent_turn import AgentToolCall, AgentTurnDecision
from ..models.observation import ObservationRecord
from ..models.task_state import CodingTaskState
from ..tools.contracts import ToolRequest, ToolResult


class TurnTermination(StrEnum):
    STAGE_COMPLETED = "STAGE_COMPLETED"
    STAGE_FAILED = "STAGE_FAILED"
    NEEDS_USER = "NEEDS_USER"
    TOOL_NOT_ALLOWED = "TOOL_NOT_ALLOWED"
    MAXIMUM_TURNS = "MAXIMUM_TURNS"
    MAXIMUM_MODEL_TOKENS = "MAXIMUM_MODEL_TOKENS"
    MODEL_USAGE_UNKNOWN = "MODEL_USAGE_UNKNOWN"
    MAXIMUM_COMMAND_SECONDS = "MAXIMUM_COMMAND_SECONDS"
    MAXIMUM_OUTPUT_BYTES = "MAXIMUM_OUTPUT_BYTES"
    MAXIMUM_REPEATED_ACTIONS = "MAXIMUM_REPEATED_ACTIONS"
    MAXIMUM_WALL_CLOCK = "MAXIMUM_WALL_CLOCK"


@dataclass(slots=True, frozen=True)
class StageGoal:
    name: str
    allowed_tools: frozenset[str]
    maximum_turns: int = 8
    maximum_repeated_actions: int = 2
    maximum_wall_clock_seconds: int = 300

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("stage goal name must be non-empty")
        if not isinstance(self.allowed_tools, frozenset) or any(
            not isinstance(item, str) or not item.strip() for item in self.allowed_tools
        ):
            raise ValueError("allowed_tools must contain tool names")
        for value in (
            self.maximum_turns,
            self.maximum_repeated_actions,
            self.maximum_wall_clock_seconds,
        ):
            if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                raise ValueError("stage limits must be positive integers")


@dataclass(slots=True, frozen=True)
class StageOutcome:
    status: str
    reason_code: TurnTermination
    reason: str
    result: dict[str, Any]
    turns: int
    tool_calls: int


class TurnExecutor(Protocol):
    observations: Any

    def request_execution(
        self, state: CodingTaskState, request: ToolRequest, *, reason: str = ...
    ) -> ToolResult:
        ...

    def approve_and_execute(
        self, state: CodingTaskState, request: ToolRequest
    ) -> ToolResult:
        ...


TurnDecider = Callable[[StageGoal, dict[str, Any]], AgentTurnDecision]
ApprovalHandler = Callable[[CodingTaskState, ToolRequest], bool]


class AgentTurnLoop:
    def __init__(
        self,
        state: CodingTaskState,
        executor: TurnExecutor,
        decide: TurnDecider,
        *,
        approval_handler: ApprovalHandler | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.state = state
        self.executor = executor
        self.decide = decide
        self.approval_handler = approval_handler
        self.clock = clock

    def run_stage(
        self, goal: StageGoal, completion_schema: dict[str, Any]
    ) -> StageOutcome:
        if not isinstance(completion_schema, dict) or not completion_schema:
            raise ValueError("completion_schema must be a non-empty object")
        started = self.clock()
        turns = 0
        tool_calls = 0
        action_history = self._prior_action_history()
        while True:
            termination = self._budget_termination(goal, turns, started)
            if termination is not None:
                return StageOutcome(
                    "failed",
                    termination,
                    self._budget_message(termination),
                    {},
                    turns,
                    tool_calls,
                )
            decision = self.decide(goal, completion_schema)
            turns += 1
            if decision.stage_result is not None:
                stage_result = decision.stage_result
                reason_code = {
                    "completed": TurnTermination.STAGE_COMPLETED,
                    "failed": TurnTermination.STAGE_FAILED,
                    "needs_user": TurnTermination.NEEDS_USER,
                }[stage_result.status]
                return StageOutcome(
                    stage_result.status,
                    reason_code,
                    stage_result.reason,
                    stage_result.result,
                    turns,
                    tool_calls,
                )
            call = decision.tool_call
            if call is None:
                raise AssertionError("validated turn omitted both actions")
            if call.tool_name not in goal.allowed_tools:
                return StageOutcome(
                    "failed",
                    TurnTermination.TOOL_NOT_ALLOWED,
                    f"tool {call.tool_name} is not allowed for stage {goal.name}",
                    {},
                    turns,
                    tool_calls,
                )
            action_digest = self._action_digest(call)
            action_history.append(action_digest)
            if self._consecutive_count(action_history, action_digest) > self._repeat_limit(
                goal
            ):
                return StageOutcome(
                    "failed",
                    TurnTermination.MAXIMUM_REPEATED_ACTIONS,
                    "identical action repetition limit reached",
                    {},
                    turns,
                    tool_calls,
                )
            request = ToolRequest(
                call.idempotency_key,
                self.state.task_id,
                call.tool_name,
                call.arguments,
                self.state.current_status.value,
            )
            result = self.executor.request_execution(
                self.state, request, reason=call.rationale
            )
            if result.error_code == ErrorCode.APPROVAL_REQUIRED.value:
                if not self.approval_handler or not self.approval_handler(
                    self.state, request
                ):
                    return StageOutcome(
                        "needs_user",
                        TurnTermination.NEEDS_USER,
                        "tool approval is required",
                        {"request_id": request.request_id},
                        turns,
                        tool_calls,
                    )
                result = self.executor.approve_and_execute(self.state, request)
            tool_calls += 1
            if result.error_code == ErrorCode.TOOL_EXECUTION_INDETERMINATE.value:
                return StageOutcome(
                    "needs_user",
                    TurnTermination.NEEDS_USER,
                    result.error_message or "tool execution requires reconciliation",
                    {},
                    turns,
                    tool_calls,
                )
            if result.error_code == ErrorCode.ACCESS_DENIED.value:
                return StageOutcome(
                    "failed",
                    TurnTermination.STAGE_FAILED,
                    result.error_message or "tool access denied",
                    {},
                    turns,
                    tool_calls,
                )

    def _budget_termination(
        self, goal: StageGoal, turns: int, started: float
    ) -> TurnTermination | None:
        budget = self.state.run_budget
        maximum_turns = budget.maximum_turns or goal.maximum_turns
        if turns >= maximum_turns:
            return TurnTermination.MAXIMUM_TURNS
        if budget.maximum_model_tokens:
            ledger = self.state.usage_ledger
            if ledger.total_tokens_known_calls < ledger.model_calls:
                return TurnTermination.MODEL_USAGE_UNKNOWN
            if ledger.total_tokens >= budget.maximum_model_tokens:
                return TurnTermination.MAXIMUM_MODEL_TOKENS
        if budget.maximum_command_seconds:
            command_ms = sum(
                item.latency_ms
                for item in self.state.tool_execution_trace
                if item.tool in {"process.run", "test.run"}
            )
            if command_ms >= budget.maximum_command_seconds * 1_000:
                return TurnTermination.MAXIMUM_COMMAND_SECONDS
        if budget.maximum_output_bytes:
            output_bytes = sum(
                item.result_bytes
                for item in self.executor.observations.list(self.state.task_id)
            )
            if output_bytes >= budget.maximum_output_bytes:
                return TurnTermination.MAXIMUM_OUTPUT_BYTES
        maximum_wall_clock = (
            budget.maximum_wall_clock_seconds or goal.maximum_wall_clock_seconds
        )
        if self.clock() - started >= maximum_wall_clock:
            return TurnTermination.MAXIMUM_WALL_CLOCK
        return None

    def _prior_action_history(self) -> list[str]:
        return [
            self._record_action_digest(item)
            for item in self.executor.observations.list(self.state.task_id)
        ]

    def _repeat_limit(self, goal: StageGoal) -> int:
        return (
            self.state.run_budget.maximum_repeated_actions
            or goal.maximum_repeated_actions
        )

    @staticmethod
    def _action_digest(call: AgentToolCall) -> str:
        arguments = json.dumps(
            call.arguments,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        request_sha256 = hashlib.sha256(arguments.encode("utf-8")).hexdigest()
        return hashlib.sha256(
            f"{call.tool_name}\0{request_sha256}".encode("utf-8")
        ).hexdigest()

    @staticmethod
    def _record_action_digest(record: ObservationRecord) -> str:
        return hashlib.sha256(
            f"{record.tool_name}\0{record.request_sha256}".encode()
        ).hexdigest()

    @staticmethod
    def _consecutive_count(history: list[str], digest: str) -> int:
        count = 0
        for item in reversed(history):
            if item != digest:
                break
            count += 1
        return count

    @staticmethod
    def _budget_message(reason: TurnTermination) -> str:
        return {
            TurnTermination.MAXIMUM_TURNS: "stage turn limit reached",
            TurnTermination.MAXIMUM_MODEL_TOKENS: "model token budget reached",
            TurnTermination.MODEL_USAGE_UNKNOWN: (
                "model usage is unknown, so the configured token budget cannot be enforced"
            ),
            TurnTermination.MAXIMUM_COMMAND_SECONDS: "command time budget reached",
            TurnTermination.MAXIMUM_OUTPUT_BYTES: "tool output byte budget reached",
            TurnTermination.MAXIMUM_WALL_CLOCK: "stage wall-clock budget reached",
        }[reason]
