from __future__ import annotations

import json
import unittest
from io import StringIO

from coding_agent.models.decisions import ImplementationPlan, ImplementationStep
from coding_agent.models.task_state import CodingTaskState
from coding_agent.mcp.server import McpToolServer
from coding_agent.storage.workspace import WorkspacePaths
from coding_agent.tools.executor import ToolExecutor
from coding_agent.tools.policy import ToolPermissionPolicy
from coding_agent.workflow.status import WorkflowStatus

from tests.support import WorkspaceTestCase


class McpServerTests(WorkspaceTestCase):
    def make_server(self) -> McpToolServer:
        (self.test_root / "module.py").write_text("value = 1\n", encoding="utf-8")
        state = CodingTaskState.create("Read module", "fixture", task_id="mcp-task")
        state.implementation_plan = ImplementationPlan(
            "read module", [ImplementationStep("step-1", "read", "module.py", "read")]
        )
        state.current_status = WorkflowStatus.EDITING
        state.validate()
        paths = WorkspacePaths.create(self.test_root).ensure()
        return McpToolServer(state, ToolExecutor(ToolPermissionPolicy(paths)))

    def test_initialize_and_tools_list_are_json_rpc_contracts(self) -> None:
        server = self.make_server()
        initialized = server.handle_message({"jsonrpc": "2.0", "id": 1, "method": "initialize"})
        self.assertEqual(initialized["result"]["serverInfo"]["name"], "coding-agent-controlled-tools")
        listed = server.handle_message({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        names = {item["name"] for item in listed["result"]["tools"]}
        self.assertIn("repo.read_file", names)
        self.assertIn("repo.apply_patch", names)
        self.assertNotIn("shell.exec", names)

    def test_tools_call_uses_controller_state_and_returns_bounded_result(self) -> None:
        server = self.make_server()
        response = server.handle_message(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "repo.read_file",
                    "request_id": "read-1",
                    "arguments": {"path": "module.py"},
                },
            }
        )
        self.assertFalse(response["result"]["isError"])
        content = json.loads(response["result"]["content"][0]["text"])
        self.assertEqual(content["output"], "value = 1\n")

    def test_stdio_transport_handles_notification_without_response(self) -> None:
        server = self.make_server()
        input_stream = StringIO(
            '{"jsonrpc":"2.0","method":"notifications/initialized"}\n'
            '{"jsonrpc":"2.0","id":4,"method":"tools/list"}\n'
        )
        output_stream = StringIO()
        server.serve_forever(input_stream, output_stream)
        lines = output_stream.getvalue().splitlines()
        self.assertEqual(len(lines), 1)
        self.assertEqual(json.loads(lines[0])["id"], 4)


if __name__ == "__main__":
    unittest.main()
