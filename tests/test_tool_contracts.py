from __future__ import annotations

import unittest

from coding_agent.tools.contracts import PendingToolCall, ToolRequest


class ToolContractTests(unittest.TestCase):
    def test_pending_arguments_round_trip_and_reject_hash_tampering(self) -> None:
        request = ToolRequest(
            "request-1",
            "task-1",
            "repo.create_file",
            {"path": "new.py", "content": "value = 1\n"},
            "EDITING",
        )
        payload = {
            "request_id": request.request_id,
            "task_id": request.task_id,
            "tool_name": request.tool_name,
            "arguments_hash": request.arguments_hash(),
            "workflow_state": request.workflow_state,
            "reason": "create the planned file",
            "created_at": "2026-08-22T00:00:00+00:00",
            "arguments": dict(request.arguments),
        }
        restored = PendingToolCall.from_dict(payload)
        self.assertEqual(restored.arguments, request.arguments)

        payload["arguments"] = {"path": "other.py", "content": "value = 1\n"}
        with self.assertRaisesRegex(ValueError, "do not match"):
            PendingToolCall.from_dict(payload)

    def test_legacy_pending_call_without_arguments_remains_loadable(self) -> None:
        pending = PendingToolCall.from_dict(
            {
                "request_id": "request-1",
                "task_id": "task-1",
                "tool_name": "test.run",
                "arguments_hash": "a" * 64,
                "workflow_state": "TESTING",
                "reason": "run tests",
                "created_at": "2026-08-22T00:00:00+00:00",
            }
        )
        self.assertEqual(pending.arguments, {})


if __name__ == "__main__":
    unittest.main()
