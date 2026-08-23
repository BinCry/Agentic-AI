"""Command-line entry point for Phase 1 task and workflow operations."""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict
from pathlib import Path
from typing import Sequence

from .models.records import ActiveSkill
from .models.task_state import CodingTaskState
from .observability.trace import JsonlTraceWriter, TraceEvent
from .skills.catalog import SkillCatalog
from .skills.router import SkillRouter
from .storage.task_store import JsonTaskStore
from .storage.checkpoint_store import CheckpointStore
from .storage.workspace import WorkspacePaths
from .workflow.engine import TransitionResult, WorkflowEngine
from .workflow.runtime import run_workflow
from .workflow.status import WorkflowStatus
from .mcp.server import McpToolServer
from .tools.contracts import ToolRequest
from .tools.executor import ToolExecutor
from .tools.policy import ToolPermissionPolicy
from .evaluation.runner import EvaluationRunner
from .cli_baseline import add_baseline_parser, run_baseline_command


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="coding-agent", description="Skill-based coding agent runtime")
    parser.add_argument("--workspace", default=".", help="Workspace root; writable state stays inside it")
    parser.add_argument("--runtime-dir", default=".coding-agent", help="Workspace-relative runtime directory")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Create a persisted coding task")
    init_parser.add_argument("--issue", required=True)
    init_parser.add_argument("--repository")
    init_parser.add_argument("--task-id")
    init_parser.add_argument("--skill-root", default=".claude/skills")

    run_parser = subparsers.add_parser(
        "run", help="Start or resume the bounded coding workflow"
    )
    run_target = run_parser.add_mutually_exclusive_group(required=True)
    run_target.add_argument("--issue", help="Start a new task for this issue")
    run_target.add_argument("--task-id", help="Resume this persisted task")
    run_parser.add_argument("--repository", help="Repository label for a new task")
    run_parser.add_argument("--skill-root", default=".claude/skills")
    run_parser.add_argument("--maximum-steps", type=int, default=40)
    run_parser.add_argument("--structured-retries", type=int, default=2)
    run_parser.add_argument(
        "--model-provider",
        choices=("openai", "openrouter"),
        default="openai",
    )
    run_parser.add_argument(
        "--embedding-provider",
        choices=("deterministic", "openai"),
        default="deterministic",
    )
    run_parser.add_argument(
        "--auto-approve",
        action="store_true",
        help="Explicitly approve policy-gated mutations and tests during this run",
    )
    run_parser.add_argument(
        "--read-only",
        action="store_true",
        help="Start a new analysis task that cannot plan mutations or run tests",
    )

    show_parser = subparsers.add_parser("show", help="Show persisted task state")
    show_parser.add_argument("--task-id", required=True)

    report_parser = subparsers.add_parser(
        "report", help="Print the verified final report for a completed task"
    )
    report_parser.add_argument("--task-id", required=True)
    report_parser.add_argument("--format", choices=("json", "markdown"), default="json")

    checkpoints_parser = subparsers.add_parser(
        "checkpoints", help="List durable checkpoints for a task"
    )
    checkpoints_parser.add_argument("--task-id", required=True)

    recover_parser = subparsers.add_parser(
        "recover", help="Restore a task from its latest or selected checkpoint"
    )
    recover_parser.add_argument("--task-id", required=True)
    recover_parser.add_argument("--checkpoint-id")

    transition_parser = subparsers.add_parser("transition", help="Apply one explicit workflow transition")
    transition_parser.add_argument("--task-id", required=True)
    transition_parser.add_argument("--to", required=True, choices=[item.value for item in WorkflowStatus])
    transition_parser.add_argument("--reason", required=True)
    transition_parser.add_argument("--skill-root", default=".claude/skills")

    approval_parser = subparsers.add_parser(
        "request-approval", help="Enter WAITING_APPROVAL with an explicit resume state"
    )
    approval_parser.add_argument("--task-id", required=True)
    approval_parser.add_argument(
        "--resume-to",
        required=True,
        choices=[WorkflowStatus.EDITING.value, WorkflowStatus.FINALIZING.value],
    )
    approval_parser.add_argument("--reason", required=True)
    approval_parser.add_argument("--skill-root", default=".claude/skills")

    approve_parser = subparsers.add_parser("approve", help="Resume a task after approval")
    approve_parser.add_argument("--task-id", required=True)
    approve_parser.add_argument("--reason", default="approval granted")
    approve_parser.add_argument("--skill-root", default=".claude/skills")

    approve_tool_parser = subparsers.add_parser(
        "approve-tool", help="Approve and execute the exact pending tool request"
    )
    approve_tool_parser.add_argument("--task-id", required=True)
    approve_tool_parser.add_argument("--request-id", required=True)
    approve_tool_parser.add_argument(
        "--arguments-json",
        help="Exact request arguments; defaults to the persisted pending request",
    )

    mcp_parser = subparsers.add_parser("mcp-server", help="Serve controlled tools over JSON-RPC stdio")
    mcp_parser.add_argument("--task-id", required=True)

    skills_parser = subparsers.add_parser("skills", help="List reusable skills by workflow state")
    skills_parser.add_argument("--skill-root", default=".claude/skills")

    evaluate_parser = subparsers.add_parser(
        "evaluate", help="Run a machine-readable retrieval/task evaluation"
    )
    evaluate_parser.add_argument(
        "--benchmark", default="tests/fixtures/benchmarks/retrieval_cases.json"
    )
    evaluate_parser.add_argument("--top-k", type=int, default=5)
    evaluate_parser.add_argument("--task-id", action="append", default=[])
    add_baseline_parser(subparsers)
    return parser


def _runtime(args: argparse.Namespace) -> tuple[WorkspacePaths, JsonTaskStore, JsonlTraceWriter]:
    paths = WorkspacePaths.create(args.workspace, args.runtime_dir).ensure()
    return paths, JsonTaskStore(paths), JsonlTraceWriter(paths)


def _catalog(paths: WorkspacePaths, skill_root: str) -> tuple[SkillCatalog, SkillRouter]:
    root = paths.resolve_readonly_path(skill_root, must_exist=True)
    catalog = SkillCatalog(root).load()
    return catalog, SkillRouter(catalog)


def _write_json(payload: object) -> None:
    json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


def _init(args: argparse.Namespace) -> int:
    started = time.perf_counter()
    paths, store, trace = _runtime(args)
    _, router = _catalog(paths, args.skill_root)
    repository = args.repository or paths.workspace_root.name
    state = CodingTaskState.create(args.issue, repository, task_id=args.task_id)
    definition = router.select(WorkflowStatus.ANALYZING)
    active_skill = router.as_active_skill(definition, paths.workspace_root)
    WorkflowEngine(state).transition(
        WorkflowStatus.ANALYZING,
        "task initialized and ready for issue analysis",
        active_skill=active_skill,
    )
    state_path = store.save(state)
    trace.append(
        TraceEvent(
            task_id=state.task_id,
            workflow_state=state.current_status.value,
            action="task.init",
            success=True,
            latency_ms=int((time.perf_counter() - started) * 1000),
            skill=active_skill.name,
            result_metadata={"state_path": str(state_path.relative_to(paths.workspace_root))},
        )
    )
    _write_json(state.to_dict())
    return 0


def _show(args: argparse.Namespace) -> int:
    _, store, _ = _runtime(args)
    _write_json(store.load(args.task_id).to_dict())
    return 0


def _run(args: argparse.Namespace) -> int:
    paths, store, _ = _runtime(args)
    outcome = run_workflow(
        paths,
        store,
        issue=args.issue,
        task_id=args.task_id,
        repository=args.repository,
        skill_root=args.skill_root,
        maximum_steps=args.maximum_steps,
        structured_retries=args.structured_retries,
        auto_approve=args.auto_approve,
        read_only=args.read_only,
        model_provider_name=args.model_provider,
        embedding_provider_name=args.embedding_provider,
    )
    state = outcome.state
    result = outcome.result
    _write_json(
        {
            "task_id": state.task_id,
            "status": result.status.value,
            "steps": result.steps,
            "reason": result.reason,
            "requires_approval": result.status is WorkflowStatus.WAITING_APPROVAL,
            "pending_tool_call": (
                asdict(state.pending_tool_call) if state.pending_tool_call else None
            ),
        }
    )
    if result.status is WorkflowStatus.COMPLETED:
        return 0
    if result.status is WorkflowStatus.WAITING_APPROVAL:
        return 3
    return 2


def _report(args: argparse.Namespace) -> int:
    _, store, _ = _runtime(args)
    state = store.load(args.task_id)
    if state.current_status is not WorkflowStatus.COMPLETED or state.final_report is None:
        raise ValueError("final report is available only for a completed task")
    if args.format == "markdown":
        sys.stdout.write(state.final_report.to_markdown())
    else:
        _write_json(state.final_report.to_dict())
    return 0


def _checkpoints(args: argparse.Namespace) -> int:
    paths, _, _ = _runtime(args)
    records = CheckpointStore(paths).list_records(args.task_id)
    _write_json([asdict(item) for item in records])
    return 0


def _recover(args: argparse.Namespace) -> int:
    paths, store, trace = _runtime(args)
    state = CheckpointStore(paths).restore(args.task_id, args.checkpoint_id)
    store.save(state)
    trace.append(
        TraceEvent(
            task_id=state.task_id,
            workflow_state=state.current_status.value,
            action="workflow.recover",
            success=True,
            latency_ms=0,
            input_metadata={"checkpoint_id": args.checkpoint_id or "latest"},
            result_metadata={"recovered": True},
        )
    )
    _write_json(state.to_dict())
    return 0


def _transition(args: argparse.Namespace) -> int:
    started = time.perf_counter()
    paths, store, trace = _runtime(args)
    _, router = _catalog(paths, args.skill_root)
    state = store.load(args.task_id)
    target = WorkflowStatus(args.to)
    candidates = router.candidates(target)
    active_skill = router.as_active_skill(candidates[0], paths.workspace_root) if candidates else None
    result = WorkflowEngine(state).transition(target, args.reason, active_skill=active_skill)
    return _finish_transition(
        store, trace, state, result, started, "workflow.transition", target, active_skill
    )


def _request_approval(args: argparse.Namespace) -> int:
    started = time.perf_counter()
    paths, store, trace = _runtime(args)
    _, router = _catalog(paths, args.skill_root)
    state = store.load(args.task_id)
    resume_target = WorkflowStatus(args.resume_to)
    candidates = router.candidates(WorkflowStatus.WAITING_APPROVAL)
    active_skill = router.as_active_skill(candidates[0], paths.workspace_root) if candidates else None
    result = WorkflowEngine(state).request_approval(
        resume_target, args.reason, active_skill=active_skill
    )
    return _finish_transition(
        store,
        trace,
        state,
        result,
        started,
        "workflow.request_approval",
        WorkflowStatus.WAITING_APPROVAL,
        active_skill,
        {"resume_to": resume_target.value},
    )


def _approve(args: argparse.Namespace) -> int:
    started = time.perf_counter()
    paths, store, trace = _runtime(args)
    _, router = _catalog(paths, args.skill_root)
    state = store.load(args.task_id)
    target = state.approval_return_status
    if target is None:
        raise ValueError("approval return status is missing")
    candidates = router.candidates(target)
    active_skill = router.as_active_skill(candidates[0], paths.workspace_root) if candidates else None
    result = WorkflowEngine(state).approve(args.reason, active_skill=active_skill)
    return _finish_transition(
        store, trace, state, result, started, "workflow.approve", target, active_skill
    )


def _approve_tool(args: argparse.Namespace) -> int:
    paths, store, _ = _runtime(args)
    state = store.load(args.task_id)
    if state.pending_tool_call is None:
        raise ValueError("task has no pending tool approval")
    if args.arguments_json is None:
        arguments = dict(state.pending_tool_call.arguments)
        if not arguments:
            raise ValueError("legacy pending request requires arguments-json")
    else:
        try:
            arguments = json.loads(args.arguments_json)
        except json.JSONDecodeError as exc:
            raise ValueError(f"arguments-json must be valid JSON: {exc}") from exc
    if not isinstance(arguments, dict):
        raise ValueError("arguments-json must contain an object")
    pending = state.pending_tool_call
    request = ToolRequest(
        request_id=args.request_id,
        task_id=state.task_id,
        tool_name=pending.tool_name,
        arguments=arguments,
        workflow_state=pending.workflow_state,
    )
    result = ToolExecutor(ToolPermissionPolicy(paths)).approve_and_execute(state, request)
    store.save(state)
    _write_json(asdict(result))
    return 0 if result.success else 2


def _mcp_server(args: argparse.Namespace) -> int:
    paths, store, _ = _runtime(args)
    state = store.load(args.task_id)
    server = McpToolServer(state, ToolExecutor(ToolPermissionPolicy(paths)))
    server.serve_forever(state_saver=store.save)
    return 0


def _finish_transition(
    store: JsonTaskStore,
    trace: JsonlTraceWriter,
    state: CodingTaskState,
    result: TransitionResult,
    started: float,
    action: str,
    requested_target: WorkflowStatus,
    active_skill: ActiveSkill | None,
    extra_metadata: dict[str, object] | None = None,
) -> int:
    forced_failure = result.forced_failure
    previous = result.previous
    current = result.current
    store.save(state)
    input_metadata = {"from": previous.value, "to": requested_target.value}
    if extra_metadata:
        input_metadata.update(extra_metadata)
    trace.append(
        TraceEvent(
            task_id=state.task_id,
            workflow_state=state.current_status.value,
            action=action,
            success=not forced_failure,
            latency_ms=int((time.perf_counter() - started) * 1000),
            skill=active_skill.name if active_skill else None,
            input_metadata=input_metadata,
            result_metadata={
                "forced_failure": forced_failure,
                "actual_status": current.value,
            },
            error=(state.errors[-1].message if forced_failure and state.errors else None),
        )
    )
    _write_json(state.to_dict())
    return 2 if forced_failure else 0


def _skills(args: argparse.Namespace) -> int:
    paths, _, _ = _runtime(args)
    catalog, router = _catalog(paths, args.skill_root)
    payload = {
        "skill_root": str(catalog.skill_root),
        "skill_count": len(catalog.all()),
        "routes": {
            status.value: [item.declared_name for item in router.candidates(status)]
            for status in WorkflowStatus
            if router.candidates(status)
        },
    }
    _write_json(payload)
    return 0


def _evaluate(args: argparse.Namespace) -> int:
    paths, store, _ = _runtime(args)
    states = [store.load(task_id) for task_id in args.task_id]
    report = EvaluationRunner(paths).run(args.benchmark, top_k=args.top_k, states=states)
    _write_json(report)
    return 0


def _baseline(args: argparse.Namespace) -> int:
    paths, _, _ = _runtime(args)
    report = run_baseline_command(args, paths)
    _write_json(report)
    return 0 if report["status"] == "passed" else 2


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    handlers = {
        "init": _init,
        "run": _run,
        "show": _show,
        "report": _report,
        "checkpoints": _checkpoints,
        "recover": _recover,
        "transition": _transition,
        "request-approval": _request_approval,
        "approve": _approve,
        "approve-tool": _approve_tool,
        "mcp-server": _mcp_server,
        "skills": _skills,
        "evaluate": _evaluate,
        "baseline": _baseline,
    }
    try:
        return handlers[args.command](args)
    except Exception as exc:
        json.dump({"error": type(exc).__name__, "message": str(exc)}, sys.stderr)
        sys.stderr.write("\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
