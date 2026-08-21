"""Bounded observe/decide/execute/validate coding workflow."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from ..llm.provider import LLMMessage, LLMProvider
from ..llm.structured_output import StructuredOutputService
from ..models.decisions import (
    DebugDecision,
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

    MAX_RETRIEVAL_QUERIES = 4

    DECISION_TYPES: dict[WorkflowStatus, type[Any]] = {
        WorkflowStatus.ANALYZING: IssueAnalysis,
        WorkflowStatus.PLANNING: ImplementationPlan,
        WorkflowStatus.EDITING: ToolDecision,
        WorkflowStatus.DEBUGGING: DebugDecision,
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
            elif status is WorkflowStatus.VERIFYING_EVIDENCE:
                self._verify_evidence()
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
        raw_queries = self.state.retrieval_queries or [self.state.original_issue]
        queries = list(dict.fromkeys(query.strip() for query in raw_queries if query.strip()))
        queries = queries[: self.MAX_RETRIEVAL_QUERIES]
        if not queries:
            raise OrchestrationError("repository retrieval requires at least one non-empty query")

        failures: list[str] = []
        for offset, query in enumerate(queries, start=1):
            request = ToolRequest(
                request_id=f"retrieve-{self.state.current_iteration + 1}-{offset}",
                task_id=self.state.task_id,
                tool_name="repo.retrieve",
                arguments={"query": query, "top_k": 8},
                workflow_state=self.state.current_status.value,
            )
            result = self.executor.request_execution(self.state, request)
            if not result.success:
                failures.append(result.error_message or f"query failed: {query}")

        if not self.state.retrieved_evidence:
            details = f"; errors: {' | '.join(failures)}" if failures else ""
            raise OrchestrationError(
                f"repository retrieval returned no grounded evidence for {len(queries)} query(s){details}"
            )
        self._transition(WorkflowStatus.VERIFYING_EVIDENCE, "repository evidence retrieved")

    def _verify_evidence(self) -> None:
        if not self.state.retrieved_evidence:
            raise OrchestrationError("repository evidence is required before planning")
        stale = [
            evidence.path
            for evidence in self.state.retrieved_evidence
            if not self.executor.rag.verify_evidence(evidence)
        ]
        if stale:
            raise OrchestrationError(
                f"repository evidence is stale or invalid: {sorted(set(stale))}"
            )
        self._transition(WorkflowStatus.PLANNING, "repository evidence verified")

    def _plan(self) -> None:
        self.state.implementation_plan = self._decide(ImplementationPlan)
        self.state.current_plan_step_index = 0
        self.state.completed_plan_step_ids = []
        self._transition(WorkflowStatus.EDITING, "implementation plan validated")

    def _edit(self) -> bool:
        plan = self.state.implementation_plan
        if plan is None:
            raise OrchestrationError("implementation plan is required before editing")
        if not self.state.pending_repair and self.state.current_plan_step_index >= len(plan.steps):
            self._transition(WorkflowStatus.TESTING, "implementation plan steps completed")
            return True

        step = None if self.state.pending_repair else plan.steps[self.state.current_plan_step_index]
        if step is not None and step.action == "test":
            self._transition(WorkflowStatus.TESTING, f"plan step {step.id} requires verification")
            return True

        decision = self._decide(ToolDecision)
        if step is not None:
            self._validate_tool_for_step(step.action, step.file, decision)
        request = ToolRequest(
            request_id=(
                f"repair-{self.state.current_iteration + 1}"
                if self.state.pending_repair
                else f"plan-{step.id}"
            ),
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
        if self.state.pending_repair:
            self.state.pending_repair = False
            self._transition(WorkflowStatus.TESTING, "bounded repair completed")
            return True

        self._complete_plan_step(step.id)
        if self.state.current_plan_step_index >= len(plan.steps):
            self._transition(WorkflowStatus.TESTING, "implementation plan steps completed")
        return True

    def _test(self) -> bool:
        profiles = self._test_profiles()
        current_results = self.state.test_results[self.state.test_run_start_index :]
        stage_index = len(current_results)
        if stage_index >= len(profiles):
            self._advance_after_tests()
            return True
        profile = profiles[stage_index]
        request = ToolRequest(
            request_id=f"test-{self.state.current_iteration + 1}-{stage_index + 1}-{profile}",
            task_id=self.state.task_id,
            tool_name="test.run",
            arguments={"profile": profile},
            workflow_state=self.state.current_status.value,
        )
        stage_name = "targeted" if stage_index == 0 else "broad"
        result = self.executor.request_execution(
            self.state,
            request,
            reason=f"run {stage_name} {profile} tests",
        )
        if result.error_code == "APPROVAL_REQUIRED":
            if not self._approve(request):
                return False
            result = self.executor.approve_and_execute(self.state, request)
        if not result.success:
            self._transition(WorkflowStatus.DEBUGGING, f"{stage_name} {profile} tests failed")
            return True
        if stage_index + 1 >= len(profiles):
            self._advance_after_tests()
        return True

    def _debug(self) -> None:
        decision = self._decide(DebugDecision)
        self.state.debug_root_cause = decision.root_cause
        self.state.debug_evidence = list(decision.evidence)
        self.state.debug_action = decision.next_action
        if decision.next_action == "retrieve":
            queries = decision.search_queries or self.state.retrieval_queries
            self.state.retrieval_queries = list(
                dict.fromkeys(query.strip() for query in queries if query.strip())
            )
            self.state.retrieved_evidence = []
            self._transition(WorkflowStatus.RETRIEVING, decision.rationale)
            return
        if decision.next_action == "fail":
            self._transition(WorkflowStatus.FAILED, decision.rationale)
            return
        self.state.pending_repair = True
        self._transition(WorkflowStatus.EDITING, decision.rationale)

    def _advance_after_tests(self) -> None:
        plan = self.state.implementation_plan
        if plan is None:
            raise OrchestrationError("implementation plan is required after testing")
        if self.state.current_plan_step_index < len(plan.steps):
            step = plan.steps[self.state.current_plan_step_index]
            if step.action != "test":
                raise OrchestrationError(f"plan step {step.id} was not executed before testing")
            self._complete_plan_step(step.id)
        target = (
            WorkflowStatus.EDITING
            if self.state.current_plan_step_index < len(plan.steps)
            else WorkflowStatus.REVIEWING
        )
        self._transition(target, "targeted and broad tests passed")

    def _test_profiles(self) -> list[str]:
        plan = self.state.implementation_plan
        configured = plan.expected_tests if plan else []
        allowlisted = self.executor.tests.PROFILES
        targeted = next(
            (
                profile
                for value in configured
                for profile in allowlisted
                if value.strip().lower() == profile
            ),
            "unit",
        )
        return [targeted] if targeted == "unit" else [targeted, "unit"]

    def _complete_plan_step(self, step_id: str) -> None:
        if step_id not in self.state.completed_plan_step_ids:
            self.state.completed_plan_step_ids.append(step_id)
        self.state.current_plan_step_index += 1
        self.state.touch()

    @staticmethod
    def _validate_tool_for_step(action: str, file: str, decision: ToolDecision) -> None:
        allowed = {
            "read": {"repo.list_files", "repo.read_file", "repo.search_text", "repo.find_symbols"},
            "modify": {"repo.apply_patch"},
            "create": {"repo.create_file"},
        }
        if decision.tool_name not in allowed.get(action, set()):
            raise OrchestrationError(
                f"tool {decision.tool_name} does not match plan action {action}"
            )
        requested_path = decision.arguments.get("path")
        normalized_requested = (
            requested_path.replace("\\", "/").casefold()
            if isinstance(requested_path, str)
            else requested_path
        )
        normalized_file = file.replace("\\", "/").casefold()
        if action in {"modify", "create"} and normalized_requested != normalized_file:
            raise OrchestrationError(
                f"tool path {requested_path!r} does not match plan file {file!r}"
            )

    def _review(self) -> None:
        review = self._decide(ReviewResult)
        self.state.review_findings = list(review.findings)
        if not review.approved:
            self.state.pending_repair = True
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
