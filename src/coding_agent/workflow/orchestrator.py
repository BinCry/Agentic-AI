"""Bounded observe/decide/execute/validate coding workflow."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from ..llm.provider import LLMMessage, LLMProvider
from ..llm.structured_output import StructuredOutputService
from ..models.decisions import (
    ImplementationPlan,
    IssueAnalysis,
    ReviewResult,
    TaskCompletionResult,
    ToolDecision,
)
from ..models.task_state import CodingTaskState
from ..tools.contracts import ToolRequest, ToolResult
from ..tools.executor import ToolExecutor
from ..skills.router import SkillRouter
from .engine import TransitionPreconditionError, WorkflowEngine
from .context import ContextCompactor, ContextProjector
from .status import WorkflowStatus


class OrchestrationError(RuntimeError):
    """Raised when the bounded workflow cannot produce a valid next action."""


@dataclass(slots=True, frozen=True)
class OrchestrationResult:
    status: WorkflowStatus
    steps: int
    reason: str


class PromptAssembler:
    """Build bounded, source-grounded prompts without leaking raw large state."""

    def __init__(self, *, maximum_context_chars: int = 24_000) -> None:
        self.projector = ContextProjector(ContextCompactor(maximum_context_chars))

    def assemble(self, state: CodingTaskState, decision_name: str) -> list[LLMMessage]:
        content = self.projector.project(state, decision_name)
        return [
            LLMMessage(
                role="system",
                content=(
                    "You are a bounded coding workflow decision maker. Return only the requested JSON "
                    "object. Use exact repository evidence, never invent paths, and keep actions minimal."
                ),
            ),
            LLMMessage(role="user", content=content),
        ]


class CodingWorkflowOrchestrator:
    """Run one bounded task loop while keeping side effects behind ToolExecutor."""

    DECISION_TYPES: dict[WorkflowStatus, type[Any]] = {
        WorkflowStatus.ANALYZING: IssueAnalysis,
        WorkflowStatus.PLANNING: ImplementationPlan,
        WorkflowStatus.EDITING: ToolDecision,
        WorkflowStatus.REVIEWING: ReviewResult,
        WorkflowStatus.FINALIZING: TaskCompletionResult,
    }

    def __init__(
        self,
        state: CodingTaskState,
        provider: LLMProvider,
        executor: ToolExecutor,
        *,
        maximum_steps: int = 40,
        structured_retries: int = 2,
        approval_handler: Callable[[CodingTaskState, ToolRequest], bool] | None = None,
        save_state: Callable[[CodingTaskState], Any] | None = None,
        prompt_assembler: PromptAssembler | None = None,
        skill_router: SkillRouter | None = None,
    ) -> None:
        if maximum_steps < 1:
            raise ValueError("maximum_steps must be positive")
        self.state = state
        self.provider = provider
        self.executor = executor
        self.maximum_steps = maximum_steps
        self.approval_handler = approval_handler
        self.save_state = save_state
        self.prompts = prompt_assembler or PromptAssembler()
        self.skill_router = skill_router
        self.skill_workspace = executor.policy.paths.workspace_root
        self.structured = StructuredOutputService(provider, maximum_retries=structured_retries)

    def run(self) -> OrchestrationResult:
        steps = 0
        while steps < self.maximum_steps:
            if self.state.current_status in {WorkflowStatus.COMPLETED, WorkflowStatus.FAILED}:
                return OrchestrationResult(self.state.current_status, steps, "workflow reached terminal state")
            status = self.state.current_status
            if status is WorkflowStatus.WAITING_APPROVAL:
                return OrchestrationResult(status, steps, "approval is required before continuing")
            self._select_skill(status)
            steps += 1
            if status is WorkflowStatus.ANALYZING:
                self._analyze()
            elif status is WorkflowStatus.RETRIEVING:
                self._retrieve()
            elif status is WorkflowStatus.PLANNING:
                self._plan()
            elif status is WorkflowStatus.EDITING:
                if not self._edit():
                    return OrchestrationResult(self.state.current_status, steps, "tool approval is required")
            elif status is WorkflowStatus.TESTING:
                if not self._test():
                    return OrchestrationResult(self.state.current_status, steps, "test approval is required")
            elif status is WorkflowStatus.DEBUGGING:
                self._debug()
            elif status is WorkflowStatus.REVIEWING:
                self._review()
            elif status is WorkflowStatus.FINALIZING:
                self._finalize()
            else:
                raise OrchestrationError(f"no orchestrator handler for {status.value}")
            self._save()
        raise OrchestrationError("maximum orchestrator steps exceeded")

    def _analyze(self) -> None:
        decision = self._decide(IssueAnalysis)
        self.state.normalized_problem_statement = decision.problem
        self.state.acceptance_criteria = list(decision.acceptance_criteria)
        self.state.retrieval_queries = list(decision.search_queries)
        self._transition(WorkflowStatus.RETRIEVING, "issue analysis completed")

    def _retrieve(self) -> None:
        query = self.state.retrieval_queries[0] if self.state.retrieval_queries else self.state.original_issue
        request = ToolRequest(
            request_id=f"retrieve-{self.state.current_iteration + 1}",
            task_id=self.state.task_id,
            tool_name="repo.retrieve",
            arguments={"query": query, "top_k": 8},
            workflow_state=self.state.current_status.value,
        )
        result = self.executor.request_execution(self.state, request)
        if not result.success:
            raise OrchestrationError(result.error_message or "repository retrieval failed")
        self._transition(WorkflowStatus.PLANNING, "grounded repository evidence retrieved")

    def _plan(self) -> None:
        self.state.implementation_plan = self._decide(ImplementationPlan)
        self._transition(WorkflowStatus.EDITING, "implementation plan validated")

    def _edit(self) -> bool:
        decision = self._decide(ToolDecision)
        request = ToolRequest(
            request_id=f"tool-{self.state.current_iteration + 1}",
            task_id=self.state.task_id,
            tool_name=decision.tool_name,
            arguments=decision.arguments,
            workflow_state=self.state.current_status.value,
        )
        result = self.executor.request_execution(self.state, request, reason=decision.rationale)
        if result.error_code == "APPROVAL_REQUIRED":
            if not self._approve(request):
                return False
            result = self.executor.approve_and_execute(self.state, request)
        if not result.success:
            raise OrchestrationError(result.error_message or "editing tool failed")
        self._transition(WorkflowStatus.TESTING, "editing tool completed")
        return True

    def _test(self) -> bool:
        request = ToolRequest(
            request_id=f"test-{self.state.current_iteration + 1}",
            task_id=self.state.task_id,
            tool_name="test.run",
            arguments={"profile": "fixture"},
            workflow_state=self.state.current_status.value,
        )
        result = self.executor.request_execution(self.state, request, reason="run targeted fixture tests")
        if result.error_code == "APPROVAL_REQUIRED":
            if not self._approve(request):
                return False
            result = self.executor.approve_and_execute(self.state, request)
        if not result.success:
            self._transition(WorkflowStatus.DEBUGGING, "targeted tests failed")
            return True
        self._transition(WorkflowStatus.REVIEWING, "targeted tests passed")
        return True

    def _debug(self) -> None:
        self._transition(WorkflowStatus.EDITING, "bounded repair iteration")

    def _review(self) -> None:
        review = self._decide(ReviewResult)
        self.state.review_findings = list(review.findings)
        self._transition(
            WorkflowStatus.FINALIZING if review.approved else WorkflowStatus.EDITING,
            "review approved" if review.approved else "review requires repair",
        )

    def _finalize(self) -> None:
        completion = self._decide(TaskCompletionResult)
        if completion.status != "completed":
            self._transition(WorkflowStatus.FAILED, completion.summary)
            return
        self.state.final_summary = completion.summary
        self.state.final_citations = list(completion.citations)
        self.state.pr_summary = completion.pr_summary or self._build_pr_summary(completion.summary)
        diff_request = ToolRequest(
            request_id=f"diff-{self.state.current_iteration + 1}",
            task_id=self.state.task_id,
            tool_name="git.diff",
            arguments={},
            workflow_state=self.state.current_status.value,
        )
        diff_result = self.executor.request_execution(self.state, diff_request)
        if diff_result.success and isinstance(diff_result.output, str) and diff_result.output.strip():
            self.state.final_diff = diff_result.output
        else:
            self.state.final_diff = "\n".join(item.patch for item in self.state.patches if item.applied)
        if not self.state.final_diff.strip():
            raise OrchestrationError("final diff is unavailable")
        self._transition(WorkflowStatus.COMPLETED, "completion invariants satisfied")

    def _build_pr_summary(self, summary: str) -> str:
        files = ", ".join(self.state.modified_files) or "none"
        citations = ", ".join(self.state.final_citations) or "none"
        return f"{summary}\nModified files: {files}\nCitations: {citations}"

    def _decide(self, model_type: type[Any]) -> Any:
        result = self.structured.generate(
            model_type,
            self.prompts.assemble(self.state, model_type.__name__),
        )
        return result.value

    def _approve(self, request: ToolRequest) -> bool:
        return bool(self.approval_handler and self.approval_handler(self.state, request))

    def _transition(self, target: WorkflowStatus, reason: str) -> None:
        result = WorkflowEngine(self.state).transition(
            target, reason, active_skill=self.state.active_skill
        )
        if result.forced_failure:
            raise OrchestrationError(self.state.errors[-1].message)

    def _save(self) -> None:
        if self.save_state:
            self.save_state(self.state)

    def _select_skill(self, status: WorkflowStatus) -> None:
        if self.skill_router is None:
            return
        definition = self.skill_router.select(status)
        self.state.active_skill = self.skill_router.as_active_skill(
            definition, self.skill_workspace
        )
        self.state.touch()
