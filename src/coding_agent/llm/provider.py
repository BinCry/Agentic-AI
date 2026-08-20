"""Provider-neutral language model interface."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, Sequence, runtime_checkable


@dataclass(slots=True, frozen=True)
class LLMMessage:
    role: str
    content: str


@dataclass(slots=True, frozen=True)
class LLMResponse:
    content: str
    model: str
    finish_reason: str | None = None
    usage: dict[str, int] = field(default_factory=dict)
    provider_metadata: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class LLMProvider(Protocol):
    """A model provider capable of returning one complete text response."""

    @property
    def provider_name(self) -> str:
        ...

    def complete(self, messages: Sequence[LLMMessage]) -> LLMResponse:
        ...
