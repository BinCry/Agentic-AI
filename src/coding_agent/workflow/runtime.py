"""Production construction and execution for the persisted coding workflow."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from ..errors import ErrorCode
from ..llm.openai_client import OpenAIClientError
from ..llm.openai_provider import OpenAIResponsesProvider
from ..llm.provider import LLMProvider
from ..models.task_state import CodingTaskState
from ..rag.embeddings import EmbeddingProvider, OpenAIEmbeddingProvider
from ..skills.catalog import SkillCatalog
from ..skills.router import SkillRouter
from ..storage.task_store import JsonTaskStore
from ..storage.workspace import WorkspacePaths
from ..tools.executor import ToolExecutor
from ..tools.contracts import ToolRequest
from ..tools.policy import ToolPermissionPolicy
from .engine import WorkflowEngine
from .orchestrator import CodingWorkflowOrchestrator, OrchestrationError, OrchestrationResult
from .status import WorkflowStatus


@dataclass(slots=True, frozen=True)
class WorkflowRunOutcome:
    state: CodingTaskState
    result: OrchestrationResult


def run_workflow(
    paths: WorkspacePaths,
    store: JsonTaskStore,
    *,
    issue: str | None = None,
    task_id: str | None = None,
    repository: str | None = None,
    skill_root: str = ".claude/skills",
    maximum_steps: int = 40,
    structured_retries: int = 2,
    auto_approve: bool = False,
    embedding_provider_name: str = "deterministic",
    environment: Mapping[str, str] | None = None,
    provider: LLMProvider | None = None,
) -> WorkflowRunOutcome:
    """Start or resume one bounded run and persist every attempted step."""
    if (issue is None) == (task_id is None):
        raise ValueError("exactly one of issue or task_id is required")
    if task_id is not None and repository is not None:
        raise ValueError("repository is valid only when starting a new task")
    if not 1 <= maximum_steps <= 200:
        raise ValueError("maximum_steps must be between 1 and 200")
    if not 0 <= structured_retries <= 8:
        raise ValueError("structured_retries must be between 0 and 8")

    root = paths.resolve_workspace_path(skill_root, must_exist=True)
    router = SkillRouter(SkillCatalog(root).load())
    model_provider = provider or OpenAIResponsesProvider.from_env(environment)
    embedding_provider = _embedding_provider(embedding_provider_name, environment)
    state = (
        _create_task(paths, store, router, issue, repository)
        if issue is not None
        else store.load(task_id or "")
    )
    executor = ToolExecutor(
        ToolPermissionPolicy(paths),
        embedding_provider=embedding_provider,
    )
    if auto_approve and state.pending_tool_call is not None:
        _approve_pending(executor, state)
        store.save(state)
    orchestrator = CodingWorkflowOrchestrator(
        state,
        model_provider,
        executor,
        maximum_steps=maximum_steps,
        structured_retries=structured_retries,
        approval_handler=(lambda _state, _request: True) if auto_approve else None,
        save_state=store.save,
        skill_router=router,
    )
    try:
        result = orchestrator.run()
    except (OpenAIClientError, OrchestrationError) as exc:
        if state.current_status not in {WorkflowStatus.COMPLETED, WorkflowStatus.FAILED}:
            WorkflowEngine(state).fail(ErrorCode.TASK_FAILED, str(exc))
        store.save(state)
        result = OrchestrationResult(state.current_status, orchestrator.steps_run, str(exc))
    return WorkflowRunOutcome(state, result)


def _create_task(
    paths: WorkspacePaths,
    store: JsonTaskStore,
    router: SkillRouter,
    issue: str,
    repository: str | None,
) -> CodingTaskState:
    state = CodingTaskState.create(issue, repository or paths.workspace_root.name)
    definition = router.select(WorkflowStatus.ANALYZING)
    active_skill = router.as_active_skill(definition, paths.workspace_root)
    WorkflowEngine(state).transition(
        WorkflowStatus.ANALYZING,
        "task initialized and ready for issue analysis",
        active_skill=active_skill,
    )
    store.save(state)
    return state


def _embedding_provider(
    name: str,
    environment: Mapping[str, str] | None,
) -> EmbeddingProvider | None:
    if name == "deterministic":
        return None
    if name == "openai":
        return OpenAIEmbeddingProvider.from_env(environment)
    raise ValueError(f"unsupported embedding provider: {name}")


def _approve_pending(executor: ToolExecutor, state: CodingTaskState) -> None:
    pending = state.pending_tool_call
    if pending is None:
        return
    if not pending.arguments:
        raise ValueError("legacy pending request requires explicit approve-tool arguments")
    request = ToolRequest(
        pending.request_id,
        pending.task_id,
        pending.tool_name,
        dict(pending.arguments),
        pending.workflow_state,
    )
    executor.approve_and_execute(state, request)
