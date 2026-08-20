"""Core package for the skill-based coding agent."""

from .models.task_state import CodingTaskState
from .workflow.status import WorkflowStatus

__all__ = ["CodingTaskState", "WorkflowStatus"]

__version__ = "0.1.0"
