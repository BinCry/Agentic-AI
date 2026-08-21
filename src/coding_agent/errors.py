"""Stable error codes and recovery metadata shared across the coding agent."""

from __future__ import annotations

from enum import StrEnum


class ErrorCode(StrEnum):
    ACCESS_DENIED = "ACCESS_DENIED"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    INVALID_MODEL_OUTPUT = "INVALID_MODEL_OUTPUT"
    MAX_ITERATIONS = "MAX_ITERATIONS"
    MAX_REPAIR_ITERATIONS = "MAX_REPAIR_ITERATIONS"
    MAX_RETRIEVAL_RETRIES = "MAX_RETRIEVAL_RETRIES"
    PATCH_CONFLICT = "PATCH_CONFLICT"
    RETRIEVAL_EMPTY = "RETRIEVAL_EMPTY"
    RETRIEVAL_FAILED = "RETRIEVAL_FAILED"
    TASK_FAILED = "TASK_FAILED"
    TEST_FAILED = "TEST_FAILED"
    TEST_TIMEOUT = "TEST_TIMEOUT"
    TOOL_GROUNDING_REQUIRED = "TOOL_GROUNDING_REQUIRED"
    TOOL_IO_ERROR = "TOOL_IO_ERROR"
    TOOL_REJECTED = "TOOL_REJECTED"
    TOOL_REQUEST_INVALID = "TOOL_REQUEST_INVALID"


RECOVERABLE_ERRORS = frozenset(
    {
        ErrorCode.PATCH_CONFLICT,
        ErrorCode.RETRIEVAL_EMPTY,
        ErrorCode.RETRIEVAL_FAILED,
        ErrorCode.TEST_FAILED,
        ErrorCode.TEST_TIMEOUT,
        ErrorCode.TOOL_GROUNDING_REQUIRED,
    }
)


def is_recoverable(code: ErrorCode | str) -> bool:
    try:
        normalized = ErrorCode(code)
    except (TypeError, ValueError):
        return False
    return normalized in RECOVERABLE_ERRORS


def normalize_error_code(code: ErrorCode | str) -> str:
    try:
        return ErrorCode(code).value
    except (TypeError, ValueError):
        return str(code)
