"""Bounded state transitions for one coding task."""

from __future__ import annotations

from dataclasses import dataclass

from ..errors import ErrorCode, is_recoverable, normalize_error_code
from ..models.records import ActiveSkill, ErrorRecord
from ..models.task_state import CodingTaskState, utc_now
from .status import WorkflowStatus, can_transition


class InvalidTransitionError(RuntimeError):
    """Raised when a requested workflow transition is not allowed."""


class TransitionPreconditionError(InvalidTransitionError):
    """Raised when task evidence is insufficient for a valid transition."""


@dataclass(slots=True, frozen=True)
class TransitionResult:
    previous: WorkflowStatus
    current: WorkflowStatus
    reason: str
    forced_failure: bool = False


class WorkflowEngine:
    def __init__(self, state: CodingTaskState) -> None:
        self.state = state

    def transition(
        self,
        target: WorkflowStatus,
        reason: str,
        *,
        active_skill: ActiveSkill | None = None,
    ) -> TransitionResult:
        return self._transition(
            target,
            reason,
            active_skill=active_skill,
            approval_granted=False,
            approval_requested=False,
        )

    def _transition(
        self,
        target: WorkflowStatus,
        reason: str,
        *,
        active_skill: ActiveSkill | None = None,
        approval_granted: bool,
        approval_requested: bool,
    ) -> TransitionResult:
        previous = self.state.current_status
        if not can_transition(previous, target):
            raise InvalidTransitionError(f"transition {previous.value} -> {target.value} is not allowed")
        if (
            previous is WorkflowStatus.WAITING_APPROVAL
            and target in {WorkflowStatus.EDITING, WorkflowStatus.FINALIZING}
            and not approval_granted
        ):
            raise InvalidTransitionError("WAITING_APPROVAL can resume only through approve()")
        if target is WorkflowStatus.WAITING_APPROVAL and not approval_requested:
            raise InvalidTransitionError("WAITING_APPROVAL can be entered only through request_approval()")
        if target is WorkflowStatus.FAILED:
            if self.state.current_iteration < self.state.maximum_iterations:
                self.state.current_iteration += 1
            self._set_failed(ErrorCode.TASK_FAILED, reason)
            self.state.validate()
            return TransitionResult(previous=previous, current=target, reason=reason)
        if self.state.current_iteration >= self.state.maximum_iterations:
            return self._fail_for_limit(
                ErrorCode.MAX_ITERATIONS,
                "maximum workflow iterations exceeded",
                reason,
            )
        self._validate_preconditions(target)
        if previous is WorkflowStatus.DEBUGGING and target is WorkflowStatus.EDITING:
            if self.state.current_repair_iteration >= self.state.maximum_repair_iterations:
                return self._fail_for_limit(
                    ErrorCode.MAX_REPAIR_ITERATIONS,
                    "maximum repair iterations exceeded",
                    reason,
                )
            self.state.current_repair_iteration += 1
        self.state.current_iteration += 1
        self.state.current_status = target
        if target is WorkflowStatus.TESTING and previous is not WorkflowStatus.WAITING_APPROVAL:
            self.state.test_run_start_index = len(self.state.test_results)
        if previous is WorkflowStatus.WAITING_APPROVAL and approval_granted:
            self.state.approval_return_status = None
        self.state.active_skill = active_skill
        self.state.touch()
        self.state.validate()
        return TransitionResult(previous=previous, current=target, reason=reason)

    def record_retrieval_failure(
        self,
        message: str,
        *,
        code: ErrorCode = ErrorCode.RETRIEVAL_EMPTY,
    ) -> bool:
        if self.state.current_status not in {
            WorkflowStatus.RETRIEVING,
            WorkflowStatus.VERIFYING_EVIDENCE,
        }:
            raise InvalidTransitionError(
                "retrieval failures can be recorded only while retrieving or verifying evidence"
            )
        if self.state.retrieval_retry_count >= self.state.maximum_retrieval_retries:
            self._set_failed(
                ErrorCode.MAX_RETRIEVAL_RETRIES,
                "maximum retrieval retries exceeded",
            )
            return False
        self.state.retrieval_retry_count += 1
        self.record_error(code, message)
        return True

    def record_error(
        self,
        code: ErrorCode | str,
        message: str,
        *,
        recoverable: bool | None = None,
    ) -> None:
        normalized = normalize_error_code(code)
        self.state.errors.append(
            ErrorRecord(
                code=normalized,
                message=message,
                workflow_state=self.state.current_status.value,
                created_at=utc_now(),
                recoverable=is_recoverable(normalized) if recoverable is None else recoverable,
            )
        )
        self.state.touch()

    def fail(self, code: ErrorCode | str, message: str) -> None:
        if self.state.current_status in {WorkflowStatus.COMPLETED, WorkflowStatus.FAILED}:
            raise InvalidTransitionError("terminal task cannot be failed again")
        self._set_failed(code, message)
        self.state.validate()

    def request_approval(
        self,
        next_status: WorkflowStatus,
        reason: str,
        *,
        active_skill: ActiveSkill | None = None,
    ) -> TransitionResult:
        if next_status not in {
            WorkflowStatus.EDITING,
            WorkflowStatus.TESTING,
            WorkflowStatus.DEBUGGING,
            WorkflowStatus.FINALIZING,
        }:
            raise InvalidTransitionError("approval can resume only an executable workflow state")
        self._validate_preconditions(next_status)
        previous_return_status = self.state.approval_return_status
        self.state.approval_return_status = next_status
        try:
            result = self._transition(
                WorkflowStatus.WAITING_APPROVAL,
                reason,
                active_skill=active_skill,
                approval_granted=False,
                approval_requested=True,
            )
        except Exception:
            self.state.approval_return_status = previous_return_status
            raise
        if result.current is not WorkflowStatus.WAITING_APPROVAL:
            self.state.approval_return_status = None
            self.state.touch()
        return result

    def approve(
        self,
        reason: str = "approval granted",
        *,
        active_skill: ActiveSkill | None = None,
    ) -> TransitionResult:
        if self.state.current_status is not WorkflowStatus.WAITING_APPROVAL:
            raise InvalidTransitionError("task is not waiting for approval")
        target = self.state.approval_return_status
        if target is None:
            raise InvalidTransitionError("approval return status is missing")
        return self._transition(
            target,
            reason,
            active_skill=active_skill,
            approval_granted=True,
            approval_requested=False,
        )

    def _fail_for_limit(
        self,
        code: ErrorCode | str,
        message: str,
        reason: str,
    ) -> TransitionResult:
        previous = self.state.current_status
        self._set_failed(code, message)
        return TransitionResult(
            previous=previous,
            current=WorkflowStatus.FAILED,
            reason=reason,
            forced_failure=True,
        )

    def _set_failed(self, code: ErrorCode | str, message: str) -> None:
        normalized = normalize_error_code(code)
        if not (
            self.state.errors
            and self.state.errors[-1].code == normalized
            and self.state.errors[-1].message == message
        ):
            self.state.errors.append(
                ErrorRecord(
                    code=normalized,
                    message=message,
                    workflow_state=self.state.current_status.value,
                    created_at=utc_now(),
                    recoverable=False,
                )
            )
        self.state.current_status = WorkflowStatus.FAILED
        self.state.approval_return_status = None
        self.state.touch()

    def _validate_preconditions(self, target: WorkflowStatus) -> None:
        errors: list[str] = []
        if target is WorkflowStatus.EDITING and self.state.implementation_plan is None:
            errors.append("implementation plan is required before EDITING")
        if target in {WorkflowStatus.REVIEWING, WorkflowStatus.FINALIZING, WorkflowStatus.COMPLETED}:
            if not self._tests_passed():
                errors.append(f"passing test results are required before {target.value}")
        if target in {WorkflowStatus.FINALIZING, WorkflowStatus.COMPLETED} and any(
            finding.severity in {"high", "critical"} for finding in self.state.review_findings
        ):
            errors.append(f"blocking review findings must be resolved before {target.value}")
        if target is WorkflowStatus.COMPLETED and not self.state.final_summary.strip():
            errors.append("final summary is required before COMPLETED")
        if target is WorkflowStatus.COMPLETED and not self.state.final_diff.strip():
            errors.append("final diff is required before COMPLETED")
        if target is WorkflowStatus.COMPLETED and not self.state.pr_summary.strip():
            errors.append("PR summary is required before COMPLETED")
        if target is WorkflowStatus.COMPLETED and not self.state.final_citations:
            errors.append("final citations are required before COMPLETED")
        if target is WorkflowStatus.COMPLETED and self.state.final_report is None:
            errors.append("structured final report is required before COMPLETED")
        if target is WorkflowStatus.COMPLETED and not self.state.acceptance_criteria:
            errors.append("acceptance criteria are required before COMPLETED")
        if target is WorkflowStatus.COMPLETED and not self.state.retrieved_evidence:
            errors.append("repository evidence is required before COMPLETED")
        if target is WorkflowStatus.COMPLETED and not self.state.modified_files:
            errors.append("modified files are required before COMPLETED")
        if errors:
            raise TransitionPreconditionError("; ".join(errors))

    def _tests_passed(self) -> bool:
        current_results = self.state.test_results[self.state.test_run_start_index :]
        return bool(current_results) and all(
            item.exit_code == 0
            and item.failed_count == 0
            and not item.timed_out
            for item in current_results
        )
