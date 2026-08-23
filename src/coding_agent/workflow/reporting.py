"""Deterministic final-report assembly from verified workflow state."""

from __future__ import annotations

from ..models.decisions import AnalysisCompletionResult, TaskCompletionResult
from ..models.records import FinalReport, TestExecution
from ..models.task_state import CodingTaskState


class FinalReportError(ValueError):
    """Raised when a model completion conflicts with persisted task evidence."""


def build_analysis_report(
    state: CodingTaskState,
    completion: AnalysisCompletionResult,
) -> FinalReport:
    if not state.read_only:
        raise FinalReportError("analysis report requires a read_only task")
    if completion.status != "completed":
        raise FinalReportError("a successful analysis report requires completed status")
    if state.modified_files or any(item.applied for item in state.patches):
        raise FinalReportError("read-only analysis cannot contain repository mutations")
    if state.test_results:
        raise FinalReportError("read-only analysis cannot contain test executions")
    citations = _unique(completion.citations)
    if not citations:
        raise FinalReportError("a successful analysis report requires repository citations")
    # New indexes use POSIX repository paths. Normalize persisted evidence too
    # so tasks and indexes created by older Windows versions remain resumable.
    evidence_paths = {
        _normalize_repository_path(item.path) for item in state.retrieved_evidence
    }
    ungrounded = [
        citation
        for citation in citations
        if _normalize_repository_path(citation.rsplit(":", 1)[0]) not in evidence_paths
    ]
    if ungrounded:
        raise FinalReportError(
            f"analysis citations are not grounded in retrieved evidence: {ungrounded}"
        )
    return FinalReport(
        status="completed",
        summary=completion.summary,
        root_cause_or_reasoning=completion.reasoning,
        changes=["No repository files changed; this was a read-only analysis."],
        tests=["Not run; read-only analysis does not enter the testing stage."],
        review=["Verified repository evidence only; mutation review was not required."],
        evidence=citations,
        remaining_limitations=(
            _unique(completion.unresolved_findings) or ["No known limitations."]
        ),
    )


def build_final_report(
    state: CodingTaskState,
    completion: TaskCompletionResult,
) -> FinalReport:
    if completion.status != "completed":
        raise FinalReportError("a successful final report requires completed status")
    if not completion.tests_passed:
        raise FinalReportError("a successful final report requires reported passing tests")

    modified_files = _unique(state.modified_files)
    reported_files = _unique(completion.modified_files)
    if not modified_files:
        raise FinalReportError("a successful final report requires modified files")
    if set(reported_files) != set(modified_files):
        raise FinalReportError(
            "reported modified files do not match controlled tool evidence: "
            f"reported={reported_files}, actual={modified_files}"
        )

    current_tests = state.test_results[state.test_run_start_index :]
    if not current_tests or any(not _test_passed(item) for item in current_tests):
        raise FinalReportError("a successful final report requires passing current tests")

    blocking = [
        item for item in state.review_findings if item.severity in {"high", "critical"}
    ]
    if blocking:
        raise FinalReportError("a successful final report cannot contain blocking review findings")

    citations = _unique(completion.citations)
    if not citations:
        raise FinalReportError("a successful final report requires repository citations")

    return FinalReport(
        status="completed",
        summary=completion.summary,
        root_cause_or_reasoning=completion.reasoning,
        changes=_change_lines(state, modified_files),
        tests=[_test_line(item) for item in current_tests],
        review=_review_lines(state),
        evidence=citations,
        remaining_limitations=_limitation_lines(state, completion),
    )


def _change_lines(state: CodingTaskState, modified_files: list[str]) -> list[str]:
    descriptions: dict[str, list[str]] = {path: [] for path in modified_files}
    if state.implementation_plan is not None:
        for step in state.implementation_plan.steps:
            if step.action in {"modify", "create"} and step.file in descriptions:
                descriptions[step.file].append(step.description)
    return [
        f"{path}: {'; '.join(_unique(descriptions[path])) or 'modified as planned'}"
        for path in modified_files
    ]


def _test_line(execution: TestExecution) -> str:
    return (
        f"{execution.target}: PASS "
        f"({execution.passed_count} passed, {execution.failed_count} failed, "
        f"{execution.duration_ms} ms)"
    )


def _review_lines(state: CodingTaskState) -> list[str]:
    summary = state.review_summary.strip() or "Review approved with no blocking findings."
    lines = [f"Approved: {summary}"]
    for finding in state.review_findings:
        location = f"{finding.file}:{finding.line}" if finding.line else finding.file
        lines.append(
            f"{finding.severity.upper()} {location}: {finding.description} "
            "[open, non-blocking]"
        )
    return lines


def _limitation_lines(
    state: CodingTaskState,
    completion: TaskCompletionResult,
) -> list[str]:
    limitations = _unique(completion.unresolved_findings)
    for finding in state.review_findings:
        limitation = f"{finding.file}: {finding.description}"
        if limitation not in limitations:
            limitations.append(limitation)
    return limitations or ["No known limitations."]


def _test_passed(execution: TestExecution) -> bool:
    return (
        execution.exit_code == 0
        and execution.failed_count == 0
        and not execution.timed_out
    )


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value.strip() for value in values if value.strip()))


def _normalize_repository_path(value: str) -> str:
    return value.strip().replace("\\", "/").removeprefix("./")
