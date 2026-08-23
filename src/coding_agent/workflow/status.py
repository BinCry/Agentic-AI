"""Explicit workflow states and allowed transitions."""

from __future__ import annotations

from enum import StrEnum


class WorkflowStatus(StrEnum):
    CREATED = "CREATED"
    ANALYZING = "ANALYZING"
    RETRIEVING = "RETRIEVING"
    VERIFYING_EVIDENCE = "VERIFYING_EVIDENCE"
    PLANNING = "PLANNING"
    EDITING = "EDITING"
    TESTING = "TESTING"
    DEBUGGING = "DEBUGGING"
    REVIEWING = "REVIEWING"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    FINALIZING = "FINALIZING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


ALLOWED_TRANSITIONS: dict[WorkflowStatus, frozenset[WorkflowStatus]] = {
    WorkflowStatus.CREATED: frozenset({WorkflowStatus.ANALYZING, WorkflowStatus.FAILED}),
    WorkflowStatus.ANALYZING: frozenset({WorkflowStatus.RETRIEVING, WorkflowStatus.FAILED}),
    WorkflowStatus.RETRIEVING: frozenset(
        {WorkflowStatus.VERIFYING_EVIDENCE, WorkflowStatus.FAILED}
    ),
    WorkflowStatus.VERIFYING_EVIDENCE: frozenset(
        {
            WorkflowStatus.RETRIEVING,
            WorkflowStatus.PLANNING,
            WorkflowStatus.FINALIZING,
            WorkflowStatus.FAILED,
        }
    ),
    WorkflowStatus.PLANNING: frozenset(
        {
            WorkflowStatus.RETRIEVING,
            WorkflowStatus.EDITING,
            WorkflowStatus.WAITING_APPROVAL,
            WorkflowStatus.FAILED,
        }
    ),
    WorkflowStatus.EDITING: frozenset(
        {
            WorkflowStatus.RETRIEVING,
            WorkflowStatus.TESTING,
            WorkflowStatus.WAITING_APPROVAL,
            WorkflowStatus.FAILED,
        }
    ),
    WorkflowStatus.TESTING: frozenset(
        {
            WorkflowStatus.DEBUGGING,
            WorkflowStatus.EDITING,
            WorkflowStatus.REVIEWING,
            WorkflowStatus.WAITING_APPROVAL,
            WorkflowStatus.FAILED,
        }
    ),
    WorkflowStatus.DEBUGGING: frozenset(
        {
            WorkflowStatus.RETRIEVING,
            WorkflowStatus.EDITING,
            WorkflowStatus.WAITING_APPROVAL,
            WorkflowStatus.FAILED,
        }
    ),
    WorkflowStatus.REVIEWING: frozenset(
        {
            WorkflowStatus.EDITING,
            WorkflowStatus.WAITING_APPROVAL,
            WorkflowStatus.FINALIZING,
            WorkflowStatus.FAILED,
        }
    ),
    WorkflowStatus.WAITING_APPROVAL: frozenset(
        {
            WorkflowStatus.EDITING,
            WorkflowStatus.TESTING,
            WorkflowStatus.DEBUGGING,
            WorkflowStatus.FINALIZING,
            WorkflowStatus.FAILED,
        }
    ),
    WorkflowStatus.FINALIZING: frozenset({WorkflowStatus.COMPLETED, WorkflowStatus.FAILED}),
    WorkflowStatus.COMPLETED: frozenset(),
    WorkflowStatus.FAILED: frozenset(),
}


def can_transition(current: WorkflowStatus, target: WorkflowStatus) -> bool:
    return target in ALLOWED_TRANSITIONS[current]
