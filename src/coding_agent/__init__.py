"""Core package for the skill-based coding agent."""

from .errors import ErrorCode
from .models.task_state import CodingTaskState
from .workflow.status import WorkflowStatus

__all__ = ["CodingTaskState", "ErrorCode", "WorkflowStatus"]

__version__ = "0.1.0"
