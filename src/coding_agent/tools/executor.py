"""Controller-owned policy, approval and dispatch boundary for Phase 2 tools."""

from __future__ import annotations

import time
from dataclasses import asdict
from uuid import uuid4

from ..errors import ErrorCode
from ..models.records import ApprovalDecisionRecord, ToolTraceRecord
from ..models.task_state import CodingTaskState, utc_now
from ..storage.workspace import WorkspacePolicyError
from ..workflow.engine import InvalidTransitionError, WorkflowEngine
from ..workflow.status import WorkflowStatus
from .contracts import PendingToolCall, ToolRequest, ToolResult
from .contracts import ToolCategory
from .command_models import CommandRequest as ProcessCommandRequest
from .command_service import CommandService, CommandValidationError
from ..execution import ExecutionBoundaryError
from .git_service import GitToolError, ReadOnlyGitService
from .patch_service import PatchConflictError, PatchToolError, PatchService
from .policy import (
    PolicyDecision,
    ToolAccessError,
    ToolPermissionPolicy,
    ToolPolicyError,
    ToolStateError,
)
from .repository_service import RepositoryReadService, RepositoryToolError
from .test_runner import AllowlistedTestRunner, TestRunnerError
from ..rag.index import RepositoryIndex, StaleEvidenceError
from ..rag.embeddings import EmbeddingProvider
from ..storage.approval_store import ApprovalLedger
from ..storage.checkpoint_store import CheckpointStore


class ToolExecutionError(ValueError):
    """Raised when a request cannot be dispatched through the controlled boundary."""


class ToolExecutor:
    """Execute only policy-approved tools and record bounded metadata in task state."""

    def __init__(
        self,
        policy: ToolPermissionPolicy,
        *,
        embedding_provider: EmbeddingProvider | None = None,
    ) -> None:
        self.policy = policy
        self.repository = RepositoryReadService(policy.paths)
        self.rag = RepositoryIndex(policy.paths, embedding_provider=embedding_provider)
        self.patch = PatchService(policy.paths)
        self.tests = AllowlistedTestRunner(
            policy.paths, workspace_trust=policy.workspace_trust
        )
        self.commands = CommandService(policy.paths)
        self.git = ReadOnlyGitService(policy.paths)
        self.checkpoints = CheckpointStore(policy.paths)
        self.approvals = ApprovalLedger(policy.paths)

    def request_execution(
        self,
        state: CodingTaskState,
        request: ToolRequest,
        *,
        reason: str = "tool execution requires approval",
    ) -> ToolResult:
        self._check_task_and_state(state, request)
        try:
            decision = self.policy.evaluate(request)
        except ToolPolicyError as exc:
            error_code = (
                ErrorCode.ACCESS_DENIED
                if isinstance(exc, (ToolAccessError, ToolStateError))
                else ErrorCode.TOOL_REQUEST_INVALID
            )
            result = ToolResult.failure(request.tool_name, error_code.value, str(exc))
            self._trace(state, request, result, 0)
            self._record_result_error(state, result)
            state.touch()
            state.validate()
            return result
        if decision.requires_approval:
            if state.pending_tool_call is not None:
                raise ToolExecutionError("another tool approval is already pending")
            if decision.spec.category in {
                ToolCategory.MUTATION,
                ToolCategory.TEST,
                ToolCategory.PROCESS,
            }:
                file_paths = (
                    (str(request.arguments["path"]),)
                    if decision.spec.category is ToolCategory.MUTATION and "path" in request.arguments
                    else ()
                )
                self.checkpoints.create(
                    state,
                    f"before approval-gated {request.tool_name}",
                    file_paths=file_paths,
                )
            state.pending_tool_call = PendingToolCall(
                request_id=request.request_id,
                task_id=request.task_id,
                tool_name=request.tool_name,
                arguments_hash=request.arguments_hash(),
                workflow_state=request.workflow_state,
                reason=reason,
                created_at=utc_now(),
                arguments=dict(request.arguments),
            )
            WorkflowEngine(state).request_approval(
                WorkflowStatus(request.workflow_state), reason
            )
            state.touch()
            return ToolResult(
                tool_name=request.tool_name,
                success=False,
                error_code=ErrorCode.APPROVAL_REQUIRED.value,
                error_message="tool execution is waiting for approval",
                output=asdict(state.pending_tool_call),
            )
        if decision.spec.category is ToolCategory.MUTATION:
            file_paths = (
                (str(request.arguments["path"]),) if "path" in request.arguments else ()
            )
            self.checkpoints.create(
                state,
                f"before policy-allowed {request.tool_name}",
                file_paths=file_paths,
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
        approval = ApprovalDecisionRecord(
            request_id=request.request_id,
            task_id=request.task_id,
            tool_name=request.tool_name,
            arguments_hash=request.arguments_hash(),
            decision="approved",
            workflow_state=pending.workflow_state,
            reason="tool execution approved",
            created_at=utc_now(),
        )
        self.approvals.append(approval)
        state.approval_decisions.append(approval)
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
        except PatchConflictError as exc:
            result = ToolResult.failure(request.tool_name, ErrorCode.PATCH_CONFLICT.value, str(exc))
        except (ToolAccessError, WorkspacePolicyError, PermissionError) as exc:
            result = ToolResult.failure(request.tool_name, ErrorCode.ACCESS_DENIED.value, str(exc))
        except StaleEvidenceError as exc:
            result = ToolResult.failure(request.tool_name, ErrorCode.RETRIEVAL_FAILED.value, str(exc))
        except TestRunnerError as exc:
            result = ToolResult.failure(
                request.tool_name,
                ErrorCode.TOOL_REQUEST_INVALID.value,
                str(exc),
            )
        except CommandValidationError as exc:
            result = ToolResult.failure(
                request.tool_name,
                ErrorCode.TOOL_REQUEST_INVALID.value,
                str(exc),
            )
        except ExecutionBoundaryError as exc:
            result = ToolResult.failure(
                request.tool_name,
                ErrorCode.ACCESS_DENIED.value,
                str(exc),
            )
        except (RepositoryToolError, PatchToolError, GitToolError, ToolPolicyError) as exc:
            result = ToolResult.failure(request.tool_name, ErrorCode.TOOL_REJECTED.value, str(exc))
        except ToolExecutionError as exc:
            result = ToolResult.failure(
                request.tool_name,
                ErrorCode.TOOL_GROUNDING_REQUIRED.value,
                str(exc),
            )
        except OSError as exc:
            result = ToolResult.failure(request.tool_name, ErrorCode.TOOL_IO_ERROR.value, str(exc))
        self._trace(state, request, result, int((time.perf_counter() - started) * 1000))
        self._record_result_error(state, result)
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
        if request.tool_name == "repo.list_files":
            files = self.repository.list_files(
                arguments.get("path", "."),
                maximum_files=arguments.get("maximum_files", 500),
            )
            return ToolResult(request.tool_name, True, files, metadata={"files": len(files)})
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
        if request.tool_name == "repo.retrieve":
            retrieval = self.rag.retrieve_grounded_with_metrics(
                arguments["query"],
                top_k=arguments.get("top_k", 8),
                maximum_retries=state.maximum_retrieval_retries,
            )
            hits = list(retrieval.hits)
            for hit in hits:
                if not any(item.chunk_id == hit.evidence.chunk_id for item in state.retrieved_evidence):
                    state.retrieved_evidence.append(hit.evidence)
            state.retrieved_evidence.sort(
                key=lambda item: (-item.score, item.path, item.start_line, item.chunk_id)
            )
            if arguments["query"] not in state.retrieval_queries:
                state.retrieval_queries.append(arguments["query"])
            if not hits:
                return ToolResult(
                    request.tool_name,
                    False,
                    output=[],
                    error_code=ErrorCode.RETRIEVAL_EMPTY.value,
                    error_message=f"no grounded repository evidence found for query: {arguments['query']}",
                    metadata={
                        "matches": 0,
                        "retrieval_metrics": asdict(retrieval.metrics),
                    },
                )
            return ToolResult(
                request.tool_name,
                True,
                [
                    {
                        **asdict(hit.evidence),
                        "lexical_score": hit.lexical_score,
                        "vector_score": hit.vector_score,
                        "symbol_score": hit.symbol_score,
                    }
                    for hit in hits
                ],
                metadata={"matches": len(hits), "retrieval_metrics": asdict(retrieval.metrics)},
            )
        if request.tool_name == "repo.create_file":
            record = self.patch.create_file(arguments["path"], arguments["content"])
            self._record_modified_file(state, record.path)
            state.patches.append(record)
            return ToolResult(request.tool_name, True, asdict(record))
        if request.tool_name == "test.detect_framework":
            return ToolResult(request.tool_name, True, self.tests.detect_framework())
        if request.tool_name == "repo.apply_patch":
            if not any(
                self._same_workspace_path(evidence.path, arguments["path"])
                and self.rag.verify_evidence(evidence)
                for evidence in state.retrieved_evidence
            ):
                raise ToolExecutionError(
                    f"current grounded repository evidence is required before patching {arguments['path']}"
                )
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
            if execution.timed_out:
                return ToolResult(
                    request.tool_name,
                    False,
                    output=asdict(execution),
                    error_code=ErrorCode.TEST_TIMEOUT.value,
                    error_message=f"test profile timed out: {arguments['profile']}",
                    timed_out=True,
                )
            if execution.exit_code != 0 or execution.failed_count:
                return ToolResult(
                    request.tool_name,
                    False,
                    output=asdict(execution),
                    error_code=ErrorCode.TEST_FAILED.value,
                    error_message=f"test profile failed: {arguments['profile']}",
                )
            return ToolResult(request.tool_name, True, asdict(execution))
        if request.tool_name == "process.run":
            command = ProcessCommandRequest(
                executable=arguments["executable"],
                arguments=tuple(arguments.get("arguments", ())),
                cwd=arguments.get("cwd", "."),
                environment=arguments.get("environment", {}),
                timeout_seconds=arguments.get(
                    "timeout_seconds", decision.spec.timeout_seconds
                ),
                maximum_output_bytes=arguments.get(
                    "maximum_output_bytes", decision.spec.maximum_output_bytes
                ),
            )
            execution = self.commands.execute(
                self.commands.prepare(command),
                trust=self.policy.workspace_trust,
            )
            output = execution.to_dict()
            metadata = {
                "duration_ms": execution.duration_ms,
                "stdout_sha256": execution.stdout_sha256,
                "stderr_sha256": execution.stderr_sha256,
            }
            if execution.timed_out:
                return ToolResult(
                    request.tool_name,
                    False,
                    output=output,
                    error_code=ErrorCode.TEST_TIMEOUT.value,
                    error_message="process execution timed out",
                    timed_out=True,
                    truncated=execution.truncated,
                    metadata=metadata,
                )
            if execution.exit_code != 0:
                return ToolResult(
                    request.tool_name,
                    False,
                    output=output,
                    error_code=ErrorCode.TEST_FAILED.value,
                    error_message=f"process exited with code {execution.exit_code}",
                    truncated=execution.truncated,
                    metadata=metadata,
                )
            return ToolResult(
                request.tool_name,
                True,
                output,
                truncated=execution.truncated,
                metadata=metadata,
            )
        if request.tool_name == "git.status":
            return ToolResult(request.tool_name, True, self.git.status())
        if request.tool_name == "git.diff":
            return ToolResult(request.tool_name, True, self.git.diff(arguments.get("paths")))
        if request.tool_name == "git.changed_files":
            return ToolResult(request.tool_name, True, self.git.changed_files())
        raise ToolExecutionError(f"no handler is registered for {request.tool_name}")

    @staticmethod
    def _record_modified_file(state: CodingTaskState, path: str) -> None:
        if path not in state.modified_files:
            state.modified_files.append(path)

    @staticmethod
    def _record_result_error(state: CodingTaskState, result: ToolResult) -> None:
        if result.success or not result.error_code:
            return
        if result.error_code == ErrorCode.APPROVAL_REQUIRED.value:
            return
        WorkflowEngine(state).record_error(
            result.error_code,
            result.error_message or f"{result.tool_name} failed",
        )

    def _same_workspace_path(self, left: str, right: str) -> bool:
        """Compare repository-relative paths independent of Windows separators."""
        try:
            left_path = self.policy.paths.resolve_workspace_path(left)
            right_path = self.policy.paths.resolve_workspace_path(right)
        except (OSError, WorkspacePolicyError):
            return False
        return left_path == right_path

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
