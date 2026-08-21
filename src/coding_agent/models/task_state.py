"""Persistent task state kept outside the model conversation."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from .decisions import ImplementationPlan, ReviewFinding
from .records import (
    ActiveSkill,
    ApprovalDecisionRecord,
    CheckpointRecord,
    ErrorRecord,
    PatchRecord,
    RepositoryEvidence,
    TestExecution,
    ToolTraceRecord,
    records_to_dict,
)
from .validation import ModelValidationError
from ..tools.contracts import PendingToolCall
from ..workflow.status import WorkflowStatus

TASK_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(slots=True)
class CodingTaskState:
    task_id: str
    original_issue: str
    repository_identifier: str
    normalized_problem_statement: str = ""
    acceptance_criteria: list[str] = field(default_factory=list)
    current_status: WorkflowStatus = WorkflowStatus.CREATED
    current_iteration: int = 0
    maximum_iterations: int = 40
    current_repair_iteration: int = 0
    maximum_repair_iterations: int = 3
    retrieval_retry_count: int = 0
    maximum_retrieval_retries: int = 3
    active_skill: ActiveSkill | None = None
    retrieval_queries: list[str] = field(default_factory=list)
    retrieved_evidence: list[RepositoryEvidence] = field(default_factory=list)
    implementation_plan: ImplementationPlan | None = None
    current_plan_step_index: int = 0
    completed_plan_step_ids: list[str] = field(default_factory=list)
    modified_files: list[str] = field(default_factory=list)
    patches: list[PatchRecord] = field(default_factory=list)
    test_results: list[TestExecution] = field(default_factory=list)
    test_run_start_index: int = 0
    review_findings: list[ReviewFinding] = field(default_factory=list)
    errors: list[ErrorRecord] = field(default_factory=list)
    checkpoints: list[CheckpointRecord] = field(default_factory=list)
    approval_decisions: list[ApprovalDecisionRecord] = field(default_factory=list)
    tool_execution_trace: list[ToolTraceRecord] = field(default_factory=list)
    final_summary: str = ""
    final_diff: str = ""
    pr_summary: str = ""
    final_citations: list[str] = field(default_factory=list)
    approval_return_status: WorkflowStatus | None = None
    pending_tool_call: PendingToolCall | None = None
    schema_version: int = 1
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)

    @classmethod
    def create(
        cls,
        original_issue: str,
        repository_identifier: str,
        *,
        task_id: str | None = None,
        maximum_iterations: int = 40,
        maximum_repair_iterations: int = 3,
        maximum_retrieval_retries: int = 3,
    ) -> "CodingTaskState":
        state = cls(
            task_id=task_id or str(uuid4()),
            original_issue=original_issue.strip(),
            repository_identifier=repository_identifier.strip(),
            maximum_iterations=maximum_iterations,
            maximum_repair_iterations=maximum_repair_iterations,
            maximum_retrieval_retries=maximum_retrieval_retries,
        )
        state.validate()
        return state

    def validate(self) -> None:
        errors: list[str] = []
        if not isinstance(self.task_id, str) or not TASK_ID_PATTERN.fullmatch(self.task_id):
            errors.append("task_id contains unsafe characters")
        if not isinstance(self.original_issue, str) or not self.original_issue.strip():
            errors.append("original_issue must not be empty")
        if not isinstance(self.repository_identifier, str) or not self.repository_identifier.strip():
            errors.append("repository_identifier must not be empty")
        if not isinstance(self.current_status, WorkflowStatus):
            errors.append("current_status must be a WorkflowStatus")
        if self.approval_return_status is not None and not isinstance(
            self.approval_return_status, WorkflowStatus
        ):
            errors.append("approval_return_status must be a WorkflowStatus or null")
        if self.pending_tool_call is not None and not isinstance(self.pending_tool_call, PendingToolCall):
            errors.append("pending_tool_call must be a PendingToolCall or null")
        for current, maximum, label in (
            (self.current_iteration, self.maximum_iterations, "iteration"),
            (self.current_repair_iteration, self.maximum_repair_iterations, "repair iteration"),
            (self.retrieval_retry_count, self.maximum_retrieval_retries, "retrieval retry"),
        ):
            if (
                not isinstance(current, int)
                or isinstance(current, bool)
                or not isinstance(maximum, int)
                or isinstance(maximum, bool)
                or current < 0
                or maximum < 1
                or current > maximum
            ):
                errors.append(f"invalid {label} bounds")
        if (
            not isinstance(self.test_run_start_index, int)
            or isinstance(self.test_run_start_index, bool)
            or self.test_run_start_index < 0
            or self.test_run_start_index > len(self.test_results)
        ):
            errors.append("invalid test_run_start_index")
        if (
            not isinstance(self.current_plan_step_index, int)
            or isinstance(self.current_plan_step_index, bool)
            or self.current_plan_step_index < 0
        ):
            errors.append("invalid current_plan_step_index")
        if not isinstance(self.schema_version, int) or isinstance(self.schema_version, bool):
            errors.append("schema_version must be an integer")
        elif self.schema_version != 1:
            errors.append(f"unsupported schema_version: {self.schema_version}")
        for value, label in (
            (self.acceptance_criteria, "acceptance_criteria"),
            (self.retrieval_queries, "retrieval_queries"),
            (self.modified_files, "modified_files"),
            (self.final_citations, "final_citations"),
            (self.completed_plan_step_ids, "completed_plan_step_ids"),
        ):
            if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
                errors.append(f"{label} must be a list of strings")
        nested_groups = (
            (self.retrieved_evidence, RepositoryEvidence, "retrieved_evidence"),
            (self.patches, PatchRecord, "patches"),
            (self.test_results, TestExecution, "test_results"),
            (self.review_findings, ReviewFinding, "review_findings"),
            (self.errors, ErrorRecord, "errors"),
            (self.checkpoints, CheckpointRecord, "checkpoints"),
            (self.approval_decisions, ApprovalDecisionRecord, "approval_decisions"),
            (self.tool_execution_trace, ToolTraceRecord, "tool_execution_trace"),
        )
        for values, expected_type, label in nested_groups:
            if not isinstance(values, list) or any(
                not isinstance(item, expected_type) for item in values
            ):
                errors.append(f"{label} contains invalid record types")
        if self.active_skill is not None and not isinstance(self.active_skill, ActiveSkill):
            errors.append("active_skill has an invalid record type")
        if self.implementation_plan is not None and not isinstance(
            self.implementation_plan, ImplementationPlan
        ):
            errors.append("implementation_plan has an invalid record type")
        if self.implementation_plan is not None:
            plan_step_ids = [step.id for step in self.implementation_plan.steps]
            if self.current_plan_step_index > len(plan_step_ids):
                errors.append("current_plan_step_index exceeds implementation plan")
            if len(self.completed_plan_step_ids) != len(set(self.completed_plan_step_ids)):
                errors.append("completed_plan_step_ids must be unique")
            unknown_completed = set(self.completed_plan_step_ids) - set(plan_step_ids)
            if unknown_completed:
                errors.append(
                    f"completed_plan_step_ids contains unknown steps: {sorted(unknown_completed)}"
                )
        elif self.current_plan_step_index or self.completed_plan_step_ids:
            errors.append("plan-step progress requires implementation_plan")
        plan_required_states = {
            WorkflowStatus.EDITING,
            WorkflowStatus.TESTING,
            WorkflowStatus.DEBUGGING,
            WorkflowStatus.REVIEWING,
            WorkflowStatus.FINALIZING,
            WorkflowStatus.COMPLETED,
        }
        if self.current_status in plan_required_states and self.implementation_plan is None:
            errors.append(f"implementation_plan is required in {self.current_status.value}")
        if self.current_status is WorkflowStatus.WAITING_APPROVAL:
            if self.approval_return_status is None:
                errors.append("WAITING_APPROVAL requires approval_return_status")
            elif self.approval_return_status not in {
                WorkflowStatus.EDITING,
                WorkflowStatus.TESTING,
                WorkflowStatus.DEBUGGING,
                WorkflowStatus.FINALIZING,
            }:
                errors.append("WAITING_APPROVAL has an invalid approval_return_status")
            elif (
                self.approval_return_status is WorkflowStatus.EDITING
                and self.implementation_plan is None
            ):
                errors.append("implementation_plan is required before approval for EDITING")
        elif self.approval_return_status is not None:
            errors.append("approval_return_status is valid only in WAITING_APPROVAL")
        current_tests = self.test_results[self.test_run_start_index :]
        tests_passed = bool(current_tests) and all(
            item.exit_code == 0 and item.failed_count == 0 and not item.timed_out
            for item in current_tests
        )
        if self.current_status in {
            WorkflowStatus.REVIEWING,
            WorkflowStatus.FINALIZING,
            WorkflowStatus.COMPLETED,
        } and not tests_passed:
            errors.append(f"passing current test results are required in {self.current_status.value}")
        if (
            self.current_status is WorkflowStatus.WAITING_APPROVAL
            and self.approval_return_status is WorkflowStatus.FINALIZING
            and not tests_passed
        ):
            errors.append("passing current test results are required before approval for FINALIZING")
        if self.current_status in {WorkflowStatus.FINALIZING, WorkflowStatus.COMPLETED} and any(
            finding.severity in {"high", "critical"} for finding in self.review_findings
        ):
            errors.append(f"blocking review findings are invalid in {self.current_status.value}")
        if (
            self.current_status is WorkflowStatus.WAITING_APPROVAL
            and self.approval_return_status is WorkflowStatus.FINALIZING
            and any(
                finding.severity in {"high", "critical"}
                for finding in self.review_findings
            )
        ):
            errors.append("blocking review findings are invalid before approval for FINALIZING")
        if self.current_status is WorkflowStatus.COMPLETED:
            if not self.final_summary.strip():
                errors.append("COMPLETED requires final_summary")
            if not self.final_diff.strip():
                errors.append("COMPLETED requires final_diff")
            if not self.pr_summary.strip():
                errors.append("COMPLETED requires pr_summary")
            if not self.final_citations:
                errors.append("COMPLETED requires final_citations")
            if not any(item.strip() for item in self.acceptance_criteria):
                errors.append("COMPLETED requires acceptance_criteria")
            if not self.retrieved_evidence:
                errors.append("COMPLETED requires retrieved_evidence")
            if not any(item.strip() for item in self.modified_files):
                errors.append("COMPLETED requires modified_files")
        if errors:
            raise ModelValidationError(errors)

    def touch(self) -> None:
        self.updated_at = utc_now()

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["current_status"] = self.current_status.value
        data["approval_return_status"] = (
            self.approval_return_status.value if self.approval_return_status else None
        )
        data["active_skill"] = asdict(self.active_skill) if self.active_skill else None
        data["retrieved_evidence"] = records_to_dict(self.retrieved_evidence)
        data["implementation_plan"] = (
            self.implementation_plan.to_dict() if self.implementation_plan else None
        )
        data["patches"] = records_to_dict(self.patches)
        data["test_results"] = records_to_dict(self.test_results)
        data["review_findings"] = [asdict(item) for item in self.review_findings]
        data["errors"] = records_to_dict(self.errors)
        data["checkpoints"] = records_to_dict(self.checkpoints)
        data["approval_decisions"] = records_to_dict(self.approval_decisions)
        data["tool_execution_trace"] = records_to_dict(self.tool_execution_trace)
        data["pending_tool_call"] = (
            asdict(self.pending_tool_call) if self.pending_tool_call else None
        )
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CodingTaskState":
        payload = dict(data)
        payload["current_status"] = WorkflowStatus(payload["current_status"])
        approval = payload.get("approval_return_status")
        payload["approval_return_status"] = WorkflowStatus(approval) if approval else None
        active_skill = payload.get("active_skill")
        payload["active_skill"] = ActiveSkill.from_dict(active_skill) if active_skill else None
        payload["retrieved_evidence"] = [
            RepositoryEvidence.from_dict(item) for item in payload.get("retrieved_evidence", [])
        ]
        plan = payload.get("implementation_plan")
        payload["implementation_plan"] = ImplementationPlan.from_dict(plan) if plan else None
        payload["patches"] = [PatchRecord.from_dict(item) for item in payload.get("patches", [])]
        payload["test_results"] = [
            TestExecution.from_dict(item) for item in payload.get("test_results", [])
        ]
        payload["review_findings"] = [
            ReviewFinding.from_dict(item) for item in payload.get("review_findings", [])
        ]
        payload["errors"] = [ErrorRecord.from_dict(item) for item in payload.get("errors", [])]
        payload["checkpoints"] = [
            CheckpointRecord.from_dict(item) for item in payload.get("checkpoints", [])
        ]
        payload["approval_decisions"] = [
            ApprovalDecisionRecord.from_dict(item)
            for item in payload.get("approval_decisions", [])
        ]
        payload["tool_execution_trace"] = [
            ToolTraceRecord.from_dict(item) for item in payload.get("tool_execution_trace", [])
        ]
        pending = payload.get("pending_tool_call")
        payload["pending_tool_call"] = PendingToolCall.from_dict(pending) if pending else None
        state = cls(**payload)
        state.validate()
        return state
