"""Strict JSON parsing with bounded model repair attempts."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Generic, Protocol, Sequence, TypeVar

from ..models.validation import ModelValidationError
from .provider import LLMMessage, LLMProvider

T = TypeVar("T")


class StructuredModel(Protocol):
    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> Any:
        ...


class StructuredOutputError(RuntimeError):
    """Raised after all structured response attempts fail."""

    def __init__(self, errors: Sequence[str], attempts: int) -> None:
        self.errors = tuple(errors)
        self.attempts = attempts
        super().__init__(f"structured output invalid after {attempts} attempts: {errors[-1]}")


@dataclass(slots=True, frozen=True)
class StructuredOutputResult(Generic[T]):
    value: T
    attempts: int
    model: str


class StructuredOutputService:
    def __init__(self, provider: LLMProvider, *, maximum_retries: int = 2) -> None:
        if maximum_retries < 0:
            raise ValueError("maximum_retries must be non-negative")
        self.provider = provider
        self.maximum_retries = maximum_retries

    def generate(
        self,
        model_type: type[T],
        messages: Sequence[LLMMessage],
    ) -> StructuredOutputResult[T]:
        conversation = list(messages)
        errors: list[str] = []
        for attempt in range(1, self.maximum_retries + 2):
            response = self.provider.complete(conversation)
            try:
                payload = json.loads(
                    response.content,
                    parse_constant=_reject_non_standard_constant,
                    object_pairs_hook=_reject_duplicate_keys,
                )
                if not isinstance(payload, dict):
                    raise ModelValidationError(["top-level JSON value must be an object"])
                value = model_type.from_dict(payload)  # type: ignore[attr-defined]
                return StructuredOutputResult(value=value, attempts=attempt, model=response.model)
            except (json.JSONDecodeError, ModelValidationError, TypeError, ValueError) as exc:
                error = str(exc)
                errors.append(error)
                if attempt > self.maximum_retries:
                    raise StructuredOutputError(errors, attempt) from exc
                conversation.extend(
                    [
                        LLMMessage(role="assistant", content=response.content),
                        LLMMessage(
                            role="user",
                            content=(
                                "Return only one JSON object matching the requested schema. "
                                f"Validation error: {error}"
                            ),
                        ),
                    ]
                )
        raise AssertionError("unreachable")


def _reject_non_standard_constant(value: str) -> None:
    raise ValueError(f"non-standard JSON constant is not allowed: {value}")


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key is not allowed: {key}")
        result[key] = value
    return result
