"""JSON-RPC tools/list and tools/call transport for the controlled tool surface.

The core services remain vendor-neutral.  This module only translates the
allowlisted contracts to MCP-shaped JSON-RPC messages and never owns task state.
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict
from typing import Any, Callable, TextIO
from uuid import uuid4

from ..models.task_state import CodingTaskState
from ..tools.contracts import ToolRequest, ToolResult
from ..tools.executor import ToolExecutionError, ToolExecutor


class McpProtocolError(ValueError):
    """Raised for malformed JSON-RPC/MCP requests."""


class McpToolServer:
    def __init__(self, state: CodingTaskState, executor: ToolExecutor) -> None:
        self.state = state
        self.executor = executor

    def handle_message(self, message: dict[str, Any]) -> dict[str, Any] | None:
        if not isinstance(message, dict):
            raise McpProtocolError("JSON-RPC message must be an object")
        method = message.get("method")
        request_id = message.get("id")
        if not isinstance(method, str):
            raise McpProtocolError("JSON-RPC method must be a string")
        if method == "notifications/initialized":
            return None
        if method == "initialize":
            return self._response(
                request_id,
                {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": {"name": "coding-agent-controlled-tools", "version": "0.1.0"},
                },
            )
        if method == "tools/list":
            return self._response(request_id, {"tools": self._tool_definitions()})
        if method == "tools/call":
            return self._response(request_id, self._call_tool(message.get("params")))
        return self._error(request_id, -32601, f"method not found: {method}")

    def approve_pending(self, request_id: str, arguments: dict[str, Any]) -> ToolResult:
        request = ToolRequest(
            request_id=request_id,
            task_id=self.state.task_id,
            tool_name=self.state.pending_tool_call.tool_name if self.state.pending_tool_call else "",
            arguments=arguments,
            workflow_state=self.state.pending_tool_call.workflow_state if self.state.pending_tool_call else "",
        )
        return self.executor.approve_and_execute(self.state, request)

    def serve_forever(
        self,
        input_stream: TextIO = sys.stdin,
        output_stream: TextIO = sys.stdout,
        *,
        state_saver: Callable[[CodingTaskState], Any] | None = None,
    ) -> None:
        for line in input_stream:
            if not line.strip():
                continue
            try:
                message = json.loads(line)
                response = self.handle_message(message)
                if state_saver is not None:
                    state_saver(self.state)
                if response is not None:
                    output_stream.write(json.dumps(response, ensure_ascii=False, separators=(",", ":")) + "\n")
                    output_stream.flush()
            except (json.JSONDecodeError, McpProtocolError) as exc:
                response = self._error(None, -32700, str(exc))
                output_stream.write(json.dumps(response, ensure_ascii=False) + "\n")
                output_stream.flush()

    def _call_tool(self, params: Any) -> dict[str, Any]:
        if not isinstance(params, dict):
            raise McpProtocolError("tools/call params must be an object")
        name = params.get("name")
        arguments = params.get("arguments", {})
        if not isinstance(name, str) or not name:
            raise McpProtocolError("tools/call requires a tool name")
        if not isinstance(arguments, dict):
            raise McpProtocolError("tools/call arguments must be an object")
        request_id = params.get("request_id") or str(uuid4())
        if not isinstance(request_id, str):
            raise McpProtocolError("request_id must be a string")
        request = ToolRequest(
            request_id=request_id,
            task_id=self.state.task_id,
            tool_name=name,
            arguments=arguments,
            workflow_state=self.state.current_status.value,
        )
        try:
            result = self.executor.request_execution(self.state, request)
        except (ToolExecutionError, ValueError) as exc:
            result = ToolResult.failure(name, "TOOL_REQUEST_INVALID", str(exc))
        return self._tool_result(result)

    @staticmethod
    def _tool_result(result: ToolResult) -> dict[str, Any]:
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(asdict(result), ensure_ascii=False, default=str),
                }
            ],
            "isError": not result.success,
        }

    def _tool_definitions(self) -> list[dict[str, Any]]:
        definitions: list[dict[str, Any]] = []
        for spec in self.executor.policy._specs.values():  # controlled, immutable local registry
            definitions.append(
                {
                    "name": spec.name,
                    "description": f"Controlled {spec.category.value} repository tool",
                    "inputSchema": self._schema_for(spec.name),
                }
            )
        return definitions

    @staticmethod
    def _schema_for(name: str) -> dict[str, Any]:
        schemas: dict[str, dict[str, Any]] = {
            "repo.read_file": {"type": "object", "required": ["path"], "properties": {"path": {"type": "string"}}},
            "repo.search_text": {"type": "object", "required": ["query"], "properties": {"query": {"type": "string"}, "path": {"type": "string"}}},
            "repo.find_symbols": {"type": "object", "required": ["path"], "properties": {"path": {"type": "string"}}},
            "repo.retrieve": {"type": "object", "required": ["query"], "properties": {"query": {"type": "string"}, "top_k": {"type": "integer", "minimum": 1, "maximum": 100}}},
            "repo.apply_patch": {"type": "object", "required": ["path", "patch", "expected_sha256"], "properties": {"path": {"type": "string"}, "patch": {"type": "string"}, "expected_sha256": {"type": "string"}}},
            "repo.create_file": {"type": "object", "required": ["path", "content"], "properties": {"path": {"type": "string"}, "content": {"type": "string"}}},
            "test.run": {"type": "object", "required": ["profile"], "properties": {"profile": {"type": "string", "enum": ["unit", "fixture"]}}},
            "git.status": {"type": "object", "properties": {}},
            "git.diff": {"type": "object", "properties": {"paths": {"type": "array", "items": {"type": "string"}}}},
        }
        return schemas[name]

    @staticmethod
    def _response(request_id: Any, result: dict[str, Any]) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": request_id, "result": result}

    @staticmethod
    def _error(request_id: Any, code: int, message: str) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}
