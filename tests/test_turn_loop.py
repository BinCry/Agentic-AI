from __future__ import annotations

import json
import math
import unittest

from coding_agent.models.agent_turn import AgentStageResult, AgentToolCall, AgentTurnDecision
from coding_agent.models.run_accounting import RunBudget
from coding_agent.models.validation import ModelValidationError


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


if __name__ == "__main__":
    unittest.main()
