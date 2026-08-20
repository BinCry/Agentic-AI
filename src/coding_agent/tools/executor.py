"""Controller-owned policy, approval and dispatch boundary for Phase 2 tools."""

from __future__ import annotations

import time
from dataclasses import asdict
from uuid import uuid4

from ..models.records import ToolTraceRecord
from ..models.task_state import CodingTaskState, utc_now
from ..workflow.engine import InvalidTransitionError, WorkflowEngine
from ..workflow.status import WorkflowStatus
from .contracts import PendingToolCall, ToolRequest, ToolResult
from .git_service import GitToolError, ReadOnlyGitService
from .patch_service import PatchToolError, PatchService
from .policy import PolicyDecision, ToolPermissionPolicy, ToolPolicyError
from .repository_service import RepositoryReadService, RepositoryToolError
from .test_runner import AllowlistedTestRunner, TestRunnerError


class ToolExecutionError(ValueError):
    """Raised when a request cannot be dispatched through the controlled boundary."""


class ToolExecutor:
    """Execute only policy-approved tools and record bounded metadata in task state."""

    def __init__(self, policy: ToolPermissionPolicy) -> None:
        self.policy = policy
        self.repository = RepositoryReadService(policy.paths)
        self.patch = PatchService(policy.paths)
        self.tests = AllowlistedTestRunner(policy.paths)
        self.git = ReadOnlyGitService(policy.paths)

    def request_execution(
        self,
        state: CodingTaskState,
        request: ToolRequest,
        *,
        reason: str = "tool execution requires approval",
    ) -> ToolResult:
        self._check_task_and_state(state, request)
        decision = self.policy.evaluate(request)
        if decision.requires_approval:
            if state.pending_tool_call is not None:
                raise ToolExecutionError("another tool approval is already pending")
            state.pending_tool_call = PendingToolCall(
                request_id=request.request_id,
                task_id=request.task_id,
                tool_name=request.tool_name,
                arguments_hash=request.arguments_hash(),
                workflow_state=request.workflow_state,
                reason=reason,
                created_at=utc_now(),
            )
            WorkflowEngine(state).request_approval(
                WorkflowStatus(request.workflow_state), reason
            )
            state.touch()
            return ToolResult(
                tool_name=request.tool_name,
                success=False,
                error_code="APPROVAL_REQUIRED",
                error_message="tool execution is waiting for approval",
                output=asdict(state.pending_tool_call),
            )
        return self._dispatch_and_trace(state, request, decision)

    def approve_and_execute(self, state: CodingTaskState, request: ToolRequest) -> ToolResult:
        pending = state.pending_tool_call
        if state.current_status is not WorkflowStatus.WAITING_APPROVAL or pending is None:
            raise ToolExecutionError("task has no pending tool approval")
        if pending.task_id != request.task_id or pending.request_id != request.request_id:
            raise ToolExecutionError("approval request identity does not match")
        if pending.tool_name != request.tool_name or pending.arguments_hash != request.arguments_hash():
            raise ToolExecutionError("approved tool arguments do not match the pending request")
        original_request = ToolRequest(
            request_id=request.request_id,
            task_id=request.task_id,
            tool_name=request.tool_name,
            arguments=request.arguments,
            workflow_state=pending.workflow_state,
        )
        decision = self.policy.evaluate(original_request)
        if not decision.requires_approval:
            raise ToolExecutionError("pending request is no longer approval-gated")
        WorkflowEngine(state).approve("tool execution approved")
        state.pending_tool_call = None
        state.touch()
        resumed_request = ToolRequest(
            request_id=request.request_id,
            task_id=request.task_id,
            tool_name=request.tool_name,
            arguments=request.arguments,
            workflow_state=state.current_status.value,
        )
        return self._dispatch_and_trace(state, resumed_request, decision)

    def _dispatch_and_trace(
        self,
        state: CodingTaskState,
        request: ToolRequest,
        decision: PolicyDecision,
    ) -> ToolResult:
        started = time.perf_counter()
        try:
            result = self._dispatch(state, request, decision)
        except (RepositoryToolError, PatchToolError, TestRunnerError, GitToolError, ToolPolicyError) as exc:
            result = ToolResult.failure(request.tool_name, "TOOL_REJECTED", str(exc))
        except OSError as exc:
            result = ToolResult.failure(request.tool_name, "TOOL_IO_ERROR", str(exc))
        self._trace(state, request, result, int((time.perf_counter() - started) * 1000))
        state.touch()
        state.validate()
        return result

    def _dispatch(
        self,
        state: CodingTaskState,
        request: ToolRequest,
        decision: PolicyDecision,
    ) -> ToolResult:
        arguments = decision.normalized_arguments
        if request.tool_name == "repo.read_file":
            content = self.repository.read_file(arguments["path"])
            return ToolResult(request.tool_name, True, content, metadata={"bytes": len(content.encode())})
        if request.tool_name == "repo.search_text":
            matches = self.repository.search_text(
                arguments["query"],
                path=arguments.get("path", "."),
                regular_expression=bool(arguments.get("regular_expression", False)),
                maximum_matches=arguments.get("maximum_matches"),
            )
            return ToolResult(
                request.tool_name,
                True,
                [asdict(item) for item in matches],
                metadata={"matches": len(matches)},
            )
        if request.tool_name == "repo.find_symbols":
            symbols = self.repository.find_symbols(arguments["path"])
            return ToolResult(request.tool_name, True, [asdict(item) for item in symbols])
        if request.tool_name == "repo.create_file":
            record = self.patch.create_file(arguments["path"], arguments["content"])
            self._record_modified_file(state, record.path)
            state.patches.append(record)
            return ToolResult(request.tool_name, True, asdict(record))
        if request.tool_name == "repo.apply_patch":
            record = self.patch.apply_unified_patch(
                arguments["path"],
                arguments["patch"],
                expected_sha256=arguments["expected_sha256"],
            )
            self._record_modified_file(state, record.path)
            state.patches.append(record)
            return ToolResult(request.tool_name, True, asdict(record))
        if request.tool_name == "test.run":
            execution = self.tests.run(arguments["profile"], timeout_seconds=decision.spec.timeout_seconds)
            state.test_results.append(execution)
            return ToolResult(request.tool_name, execution.exit_code == 0 and not execution.timed_out, asdict(execution))
        if request.tool_name == "git.status":
            return ToolResult(request.tool_name, True, self.git.status())
        if request.tool_name == "git.diff":
            return ToolResult(request.tool_name, True, self.git.diff(arguments.get("paths")))
        raise ToolExecutionError(f"no handler is registered for {request.tool_name}")

    @staticmethod
    def _record_modified_file(state: CodingTaskState, path: str) -> None:
        if path not in state.modified_files:
            state.modified_files.append(path)

    @staticmethod
    def _check_task_and_state(state: CodingTaskState, request: ToolRequest) -> None:
        if state.task_id != request.task_id:
            raise ToolExecutionError("tool request task_id does not match task state")
        if state.current_status.value != request.workflow_state:
            raise ToolExecutionError("tool request workflow state is stale")

    @staticmethod
    def _trace(state: CodingTaskState, request: ToolRequest, result: ToolResult, latency_ms: int) -> None:
        state.tool_execution_trace.append(
            ToolTraceRecord(
                event_id=str(uuid4()),
                timestamp=utc_now(),
                workflow_state=state.current_status.value,
                skill=state.active_skill.name if state.active_skill else None,
                tool=request.tool_name,
                success=result.success,
                latency_ms=latency_ms,
                input_metadata={"arguments_hash": request.arguments_hash()},
                result_metadata={
                    "error_code": result.error_code,
                    "timed_out": result.timed_out,
                    "truncated": result.truncated,
                },
                error=result.error_message,
            )
        )
