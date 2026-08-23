"""Provider-neutral language model interface."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, Sequence, runtime_checkable


@dataclass(slots=True, frozen=True)
class LLMMessage:
    role: str
    content: str


@dataclass(slots=True, frozen=True)
class ModelUsage:
    """Numeric usage only; omitted provider usage remains explicitly unknown."""

    input_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int = 0
    total_tokens: int = 0
    input_tokens_known_calls: int = 0
    output_tokens_known_calls: int = 0
    reasoning_tokens_known_calls: int = 0
    total_tokens_known_calls: int = 0
    known_calls: int = 0
    unknown_calls: int = 1

    def __post_init__(self) -> None:
        numeric_fields = (
            self.input_tokens,
            self.output_tokens,
            self.reasoning_tokens,
            self.total_tokens,
            self.input_tokens_known_calls,
            self.output_tokens_known_calls,
            self.reasoning_tokens_known_calls,
            self.total_tokens_known_calls,
            self.known_calls,
            self.unknown_calls,
        )
        if any(
            not isinstance(value, int) or isinstance(value, bool) or value < 0
            for value in numeric_fields
        ):
            raise ValueError("model usage values must be non-negative integers")
        known_counts = (
            self.input_tokens_known_calls,
            self.output_tokens_known_calls,
            self.reasoning_tokens_known_calls,
            self.total_tokens_known_calls,
        )
        if any(count > self.known_calls for count in known_counts):
            raise ValueError("token known-call counts cannot exceed known_calls")
        if self.known_calls > 0 and not any(known_counts):
            raise ValueError("known model usage requires a reported token field")
        if any(
            known_calls == 0 and tokens != 0
            for known_calls, tokens in zip(
                known_counts,
                (
                    self.input_tokens,
                    self.output_tokens,
                    self.reasoning_tokens,
                    self.total_tokens,
                ),
                strict=True,
            )
        ):
            raise ValueError("token totals require at least one known call")
        if (
            self.known_calls > 0
            and self.input_tokens_known_calls == self.known_calls
            and self.output_tokens_known_calls == self.known_calls
            and self.total_tokens_known_calls == self.known_calls
            and self.total_tokens < self.input_tokens + self.output_tokens
        ):
            raise ValueError("total_tokens must cover input_tokens and output_tokens")

    @classmethod
    def empty(cls) -> "ModelUsage":
        return cls(unknown_calls=0)

    @classmethod
    def from_payload(cls, payload: object) -> "ModelUsage":
        if not isinstance(payload, dict):
            return cls()
        input_tokens = _usage_value(payload, "input_tokens", "prompt_tokens")
        output_tokens = _usage_value(payload, "output_tokens", "completion_tokens")
        total_tokens = _usage_value(payload, "total_tokens")
        reasoning_tokens = _reasoning_usage(payload)
        values = (input_tokens, output_tokens, reasoning_tokens, total_tokens)
        if all(value is None for value in values):
            return cls()
        if (
            input_tokens is not None
            and output_tokens is not None
            and total_tokens is not None
            and total_tokens < input_tokens + output_tokens
        ):
            total_tokens = None
        return cls(
            input_tokens=input_tokens or 0,
            output_tokens=output_tokens or 0,
            reasoning_tokens=reasoning_tokens or 0,
            total_tokens=total_tokens or 0,
            input_tokens_known_calls=int(input_tokens is not None),
            output_tokens_known_calls=int(output_tokens is not None),
            reasoning_tokens_known_calls=int(reasoning_tokens is not None),
            total_tokens_known_calls=int(total_tokens is not None),
            known_calls=1,
            unknown_calls=0,
        )

    def merge(self, other: "ModelUsage") -> "ModelUsage":
        if not isinstance(other, ModelUsage):
            raise TypeError("model usage merge requires ModelUsage")
        return ModelUsage(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            reasoning_tokens=self.reasoning_tokens + other.reasoning_tokens,
            total_tokens=self.total_tokens + other.total_tokens,
            input_tokens_known_calls=(
                self.input_tokens_known_calls + other.input_tokens_known_calls
            ),
            output_tokens_known_calls=(
                self.output_tokens_known_calls + other.output_tokens_known_calls
            ),
            reasoning_tokens_known_calls=(
                self.reasoning_tokens_known_calls
                + other.reasoning_tokens_known_calls
            ),
            total_tokens_known_calls=(
                self.total_tokens_known_calls + other.total_tokens_known_calls
            ),
            known_calls=self.known_calls + other.known_calls,
            unknown_calls=self.unknown_calls + other.unknown_calls,
        )


@dataclass(slots=True, frozen=True)
class LLMResponse:
    content: str
    model: str
    finish_reason: str | None = None
    usage: ModelUsage = field(default_factory=ModelUsage)
    provider_metadata: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class LLMProvider(Protocol):
    """A model provider capable of returning one complete text response."""

    @property
    def provider_name(self) -> str:
        ...

    def complete(self, messages: Sequence[LLMMessage]) -> LLMResponse:
        ...


def _usage_value(payload: dict[str, Any], *names: str) -> int | None:
    for name in names:
        if name not in payload:
            continue
        value = payload[name]
        return (
            value
            if isinstance(value, int) and not isinstance(value, bool) and value >= 0
            else None
        )
    return None


def _reasoning_usage(payload: dict[str, Any]) -> int | None:
    direct = _usage_value(payload, "reasoning_tokens")
    if direct is not None:
        return direct
    for name in ("output_tokens_details", "completion_tokens_details"):
        details = payload.get(name)
        if isinstance(details, dict):
            value = _usage_value(details, "reasoning_tokens")
            if value is not None:
                return value
    return None
