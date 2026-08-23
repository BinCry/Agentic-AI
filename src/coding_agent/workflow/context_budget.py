"""Priority-based context projection with conservative token estimates."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import Any


@dataclass(slots=True, frozen=True)
class ContextBudget:
    maximum_tokens: int
    maximum_chars: int

    def __post_init__(self) -> None:
        for value in (self.maximum_tokens, self.maximum_chars):
            if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                raise ValueError("context limits must be positive integers")


@dataclass(slots=True, frozen=True)
class ContextSection:
    key: str
    value: Any
    priority: int
    required: bool = False
    fallback: Any = None

    def __post_init__(self) -> None:
        if not isinstance(self.key, str) or not self.key.strip():
            raise ValueError("context section key must be non-empty")
        if not isinstance(self.priority, int) or isinstance(self.priority, bool):
            raise ValueError("context section priority must be an integer")


@dataclass(slots=True, frozen=True)
class ProjectedContext:
    payload: dict[str, Any]
    estimated_tokens: int
    serialized_chars: int
    included_sections: tuple[str, ...]
    omitted_sections: tuple[str, ...]
    truncated: bool

    def to_json(self) -> str:
        return _encode(self.payload)


class ContextBudgeter:
    """Select whole or bounded-fallback sections without raw prefix slicing."""

    def __init__(self, *, conservative_chars_per_token: int = 3) -> None:
        if (
            not isinstance(conservative_chars_per_token, int)
            or isinstance(conservative_chars_per_token, bool)
            or conservative_chars_per_token < 1
        ):
            raise ValueError("conservative_chars_per_token must be positive")
        self.chars_per_token = conservative_chars_per_token

    def project(
        self, sections: list[ContextSection], budget: ContextBudget
    ) -> ProjectedContext:
        if not isinstance(budget, ContextBudget):
            raise TypeError("budget must be ContextBudget")
        keys = [section.key for section in sections]
        if len(keys) != len(set(keys)):
            raise ValueError("context section keys must be unique")
        ordered = sorted(
            enumerate(sections),
            key=lambda item: (
                not item[1].required,
                -item[1].priority,
                item[0],
            ),
        )
        payload: dict[str, Any] = {"truncated": False}
        included: list[str] = []
        omitted: list[str] = []
        truncated = False
        for _, section in ordered:
            selected, used_fallback = self._select_value(payload, section, budget)
            if selected is _OMITTED:
                omitted.append(section.key)
                truncated = True
                continue
            payload[section.key] = selected
            included.append(section.key)
            truncated = truncated or used_fallback
        payload["truncated"] = truncated
        content = _encode(payload)
        if not self._fits(content, budget):
            raise ValueError("required context metadata exceeds configured budget")
        return ProjectedContext(
            payload=payload,
            estimated_tokens=self.estimate_tokens(content),
            serialized_chars=len(content),
            included_sections=tuple(included),
            omitted_sections=tuple(omitted),
            truncated=truncated,
        )

    def estimate_tokens(self, content: str) -> int:
        return max(1, math.ceil(len(content.encode("utf-8")) / self.chars_per_token))

    def _select_value(
        self,
        payload: dict[str, Any],
        section: ContextSection,
        budget: ContextBudget,
    ) -> tuple[Any, bool]:
        for candidate, fallback in (
            (section.value, False),
            (section.fallback, True),
        ):
            if candidate is None and fallback:
                continue
            if self._payload_fits(payload, section.key, candidate, budget):
                return candidate, fallback
        if not section.required:
            return _OMITTED, True
        fitted = self._fit_required(payload, section.key, section.fallback, budget)
        if fitted is _OMITTED:
            fitted = self._fit_required(payload, section.key, section.value, budget)
        return fitted, True

    def _fit_required(
        self,
        payload: dict[str, Any],
        key: str,
        value: Any,
        budget: ContextBudget,
    ) -> Any:
        if isinstance(value, list):
            selected: list[Any] = []
            for item in value:
                if self._payload_fits(payload, key, [*selected, item], budget):
                    selected.append(item)
                else:
                    break
            if selected or self._payload_fits(payload, key, [], budget):
                return selected
        if isinstance(value, str):
            low, high = 0, len(value)
            best: str | None = None
            while low <= high:
                midpoint = (low + high) // 2
                candidate = value[:midpoint]
                if self._payload_fits(payload, key, candidate, budget):
                    best = candidate
                    low = midpoint + 1
                else:
                    high = midpoint - 1
            if best is not None:
                return best
        if self._payload_fits(payload, key, {"truncated": True}, budget):
            return {"truncated": True}
        return _OMITTED

    def _payload_fits(
        self,
        payload: dict[str, Any],
        key: str,
        value: Any,
        budget: ContextBudget,
    ) -> bool:
        return self._fits(_encode({**payload, key: value}), budget)

    def _fits(self, content: str, budget: ContextBudget) -> bool:
        return (
            len(content) <= budget.maximum_chars
            and self.estimate_tokens(content) <= budget.maximum_tokens
        )


_OMITTED = object()


def _encode(payload: dict[str, Any]) -> str:
    return json.dumps(
        payload,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )
