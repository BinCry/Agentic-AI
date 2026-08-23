from __future__ import annotations

import json
import math
import unittest
from collections.abc import Callable
from typing import Any

from coding_agent.errors import ErrorCode
from coding_agent.models.agent_turn import AgentStageResult, AgentToolCall, AgentTurnDecision
from coding_agent.models.run_accounting import RunBudget, UsageLedger
from coding_agent.models.task_state import CodingTaskState
from coding_agent.models.validation import ModelValidationError
from coding_agent.tools.contracts import ToolRequest, ToolResult
from coding_agent.workflow.status import WorkflowStatus
from coding_agent.workflow.turn_loop import AgentTurnLoop, StageGoal, TurnTermination


class AgentTurnContractTests(unittest.TestCase):
    def test_tool_call_round_trips_as_one_json_safe_action(self) -> None:
        decision = AgentTurnDecision.from_dict(
            {
                "tool_call": {
                    "idempotency_key": "task-1:turn-2:read",
                    "tool_name": "repo.read_file",
                    "arguments": {"path": "src/app.py"},
                    "rationale": "Inspect current implementation",
                }
            }
        )

        self.assertIsInstance(decision.tool_call, AgentToolCall)
        self.assertIsNone(decision.stage_result)
        self.assertEqual(AgentTurnDecision.from_dict(decision.to_dict()), decision)
        json.dumps(decision.to_dict(), allow_nan=False)

    def test_stage_result_round_trips_without_reasoning_payload(self) -> None:
        decision = AgentTurnDecision.from_dict(
            {
                "stage_result": {
                    "status": "completed",
                    "reason": "Grounded stage acceptance reached",
                    "result": {"citations": ["src/app.py:1-4"]},
                }
            }
        )

        self.assertIsInstance(decision.stage_result, AgentStageResult)
        self.assertNotIn("reasoning", decision.to_dict()["stage_result"])

    def test_exactly_one_action_and_strict_fields_are_required(self) -> None:
        tool = {
            "idempotency_key": "turn-1",
            "tool_name": "git.status",
            "arguments": {},
            "rationale": "Observe",
        }
        result = {"status": "completed", "reason": "Done", "result": {}}
        cases = ({}, {"tool_call": tool, "stage_result": result}, {"unknown": {}})
        for payload in cases:
            with self.subTest(payload=payload), self.assertRaises(ModelValidationError):
                AgentTurnDecision.from_dict(payload)

    def test_non_finite_or_non_json_action_payload_is_rejected(self) -> None:
        for arguments in (
            {"score": math.nan},
            {"value": object()},
            {"tuple": (1, 2)},
            {1: "coerced-key"},
        ):
            with self.subTest(arguments=arguments), self.assertRaises(ModelValidationError):
                AgentToolCall("turn-1", "repo.read_file", arguments, "Observe")

    def test_turn_and_repetition_budgets_are_backward_compatible_and_typed(self) -> None:
        legacy = RunBudget.from_dict({"maximum_model_tokens": 100})
        self.assertEqual(legacy.maximum_turns, 0)
        budget = RunBudget(maximum_turns=12, maximum_repeated_actions=2)
        self.assertEqual(RunBudget.from_dict(budget.to_dict()), budget)
        with self.assertRaisesRegex(ModelValidationError, "maximum_turns"):
            RunBudget(maximum_turns=True).validate()


class _Observations:
    def __init__(self) -> None:
        self.records: list[Any] = []

    def list(self, task_id: str) -> list[Any]:
        return [item for item in self.records if item.task_id == task_id]


class _Executor:
    def __init__(self, results: list[ToolResult]) -> None:
        self.observations = _Observations()
        self.results = list(results)
        self.requests: list[ToolRequest] = []

    def request_execution(
        self,
        state: CodingTaskState,
        request: ToolRequest,
        *,
        reason: str = "",
    ) -> ToolResult:
        del state, reason
        self.requests.append(request)
        return self.results.pop(0)

    def approve_and_execute(
        self, state: CodingTaskState, request: ToolRequest
    ) -> ToolResult:
        del state, request
        return self.results.pop(0)


def _state() -> CodingTaskState:
    state = CodingTaskState.create("Inspect repository", "D:/workspace", task_id="task-1")
    state.current_status = WorkflowStatus.ANALYZING
    return state


def _decider(
    decisions: list[AgentTurnDecision],
) -> Callable[[StageGoal, dict[str, Any]], AgentTurnDecision]:
    queued = list(decisions)

    def decide(goal: StageGoal, completion_schema: dict[str, Any]) -> AgentTurnDecision:
        del goal, completion_schema
        return queued.pop(0)

    return decide


def _call(key: str, query: str = "needle") -> AgentTurnDecision:
    return AgentTurnDecision(
        tool_call=AgentToolCall(
            key,
            "repo.search_text",
            {"query": query},
            "Gather grounded evidence",
        )
    )


class AgentTurnLoopTests(unittest.TestCase):
    def test_observes_one_tool_result_before_stage_completion(self) -> None:
        executor = _Executor([ToolResult("repo.search_text", True, {"matches": []})])
        completed = AgentTurnDecision(
            stage_result=AgentStageResult("completed", "Evidence collected", {"ok": True})
        )
        loop = AgentTurnLoop(_state(), executor, _decider([_call("turn-1"), completed]))

        outcome = loop.run_stage(
            StageGoal("analysis", frozenset({"repo.search_text"})),
            {"ok": "boolean"},
        )

        self.assertEqual(outcome.reason_code, TurnTermination.STAGE_COMPLETED)
        self.assertEqual((outcome.turns, outcome.tool_calls), (2, 1))
        self.assertEqual(len(executor.requests), 1)

    def test_stops_before_third_identical_action(self) -> None:
        executor = _Executor(
            [
                ToolResult("repo.search_text", True, {}),
                ToolResult("repo.search_text", True, {}),
            ]
        )
        loop = AgentTurnLoop(
            _state(),
            executor,
            _decider([_call("turn-1"), _call("turn-2"), _call("turn-3")]),
        )

        outcome = loop.run_stage(
            StageGoal(
                "analysis",
                frozenset({"repo.search_text"}),
                maximum_repeated_actions=2,
            ),
            {"ok": "boolean"},
        )

        self.assertEqual(
            outcome.reason_code, TurnTermination.MAXIMUM_REPEATED_ACTIONS
        )
        self.assertEqual(len(executor.requests), 2)

    def test_stops_at_turn_limit_after_tool_execution(self) -> None:
        executor = _Executor([ToolResult("repo.search_text", True, {})])
        loop = AgentTurnLoop(_state(), executor, _decider([_call("turn-1")]))

        outcome = loop.run_stage(
            StageGoal(
                "analysis", frozenset({"repo.search_text"}), maximum_turns=1
            ),
            {"ok": "boolean"},
        )

        self.assertEqual(outcome.reason_code, TurnTermination.MAXIMUM_TURNS)
        self.assertEqual((outcome.turns, outcome.tool_calls), (1, 1))

    def test_refuses_token_budget_when_provider_usage_is_unknown(self) -> None:
        state = _state()
        state.run_budget.maximum_model_tokens = 100
        state.usage_ledger = UsageLedger(model_calls=1, usage_unknown_calls=1)
        executor = _Executor([])
        called = False

        def decide(
            goal: StageGoal, completion_schema: dict[str, Any]
        ) -> AgentTurnDecision:
            del goal, completion_schema
            nonlocal called
            called = True
            raise AssertionError("decision must not run when budget cannot be enforced")

        outcome = AgentTurnLoop(state, executor, decide).run_stage(
            StageGoal("analysis", frozenset({"repo.search_text"})),
            {"ok": "boolean"},
        )

        self.assertEqual(outcome.reason_code, TurnTermination.MODEL_USAGE_UNKNOWN)
        self.assertFalse(called)

    def test_returns_needs_user_when_tool_requires_approval(self) -> None:
        executor = _Executor(
            [
                ToolResult.failure(
                    "repo.search_text",
                    ErrorCode.APPROVAL_REQUIRED.value,
                    "approval required",
                )
            ]
        )
        outcome = AgentTurnLoop(
            _state(), executor, _decider([_call("turn-1")])
        ).run_stage(
            StageGoal("analysis", frozenset({"repo.search_text"})),
            {"ok": "boolean"},
        )

        self.assertEqual(outcome.status, "needs_user")
        self.assertEqual(outcome.reason_code, TurnTermination.NEEDS_USER)
        self.assertEqual(outcome.result, {"request_id": "turn-1"})


if __name__ == "__main__":
    unittest.main()
