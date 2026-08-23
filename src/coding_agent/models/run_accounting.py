"""Typed run limits and aggregate model usage stored with task state."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .validation import ModelValidationError


def _validate_non_negative_integer(value: object, field_name: str, errors: list[str]) -> None:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        errors.append(f"{field_name} must be a non-negative integer")


def _validated_string_list(value: object, field_name: str, errors: list[str]) -> None:
    if (
        not isinstance(value, list)
        or any(not isinstance(item, str) or not item.strip() for item in value)
        or len(value) != len(set(value))
    ):
        errors.append(f"{field_name} must contain unique non-empty strings")


@dataclass(slots=True)
class RunBudget:
    """Configured limits; zero means not yet enforced by the current workflow."""

    maximum_model_tokens: int = 0
    maximum_command_seconds: int = 0
    maximum_output_bytes: int = 0
    maximum_wall_clock_seconds: int = 0
    maximum_turns: int = 0
    maximum_repeated_actions: int = 0

    def validate(self) -> None:
        errors: list[str] = []
        for field_name in (
            "maximum_model_tokens",
            "maximum_command_seconds",
            "maximum_output_bytes",
            "maximum_wall_clock_seconds",
            "maximum_turns",
            "maximum_repeated_actions",
        ):
            _validate_non_negative_integer(getattr(self, field_name), field_name, errors)
        if errors:
            raise ModelValidationError(errors)

    def to_dict(self) -> dict[str, int]:
        self.validate()
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: object) -> "RunBudget":
        if not isinstance(payload, dict):
            raise ModelValidationError(["run_budget must be an object"])
        allowed = {
            "maximum_model_tokens",
            "maximum_command_seconds",
            "maximum_output_bytes",
            "maximum_wall_clock_seconds",
            "maximum_turns",
            "maximum_repeated_actions",
        }
        unknown = set(payload) - allowed
        if unknown:
            raise ModelValidationError([f"run_budget contains unknown fields: {sorted(unknown)}"])
        budget = cls(**payload)
        budget.validate()
        return budget


@dataclass(slots=True)
class UsageLedger:
    """Aggregate provider usage without prompts, credentials, or reasoning text."""

    model_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int = 0
    total_tokens: int = 0
    latency_ms: int = 0
    providers: list[str] = field(default_factory=list)
    models: list[str] = field(default_factory=list)

    def validate(self) -> None:
        errors: list[str] = []
        for field_name in (
            "model_calls",
            "input_tokens",
            "output_tokens",
            "reasoning_tokens",
            "total_tokens",
            "latency_ms",
        ):
            _validate_non_negative_integer(getattr(self, field_name), field_name, errors)
        if not errors and self.total_tokens < self.input_tokens + self.output_tokens:
            errors.append("total_tokens must cover input_tokens and output_tokens")
        _validated_string_list(self.providers, "providers", errors)
        _validated_string_list(self.models, "models", errors)
        if errors:
            raise ModelValidationError(errors)

    def record(
        self,
        *,
        provider: str,
        model: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        reasoning_tokens: int = 0,
        total_tokens: int | None = None,
        latency_ms: int = 0,
    ) -> None:
        self.validate()
        if not isinstance(provider, str) or not provider.strip():
            raise ModelValidationError(["provider must be a non-empty string"])
        if not isinstance(model, str) or not model.strip():
            raise ModelValidationError(["model must be a non-empty string"])
        values = {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "reasoning_tokens": reasoning_tokens,
            "latency_ms": latency_ms,
        }
        errors: list[str] = []
        for field_name, value in values.items():
            _validate_non_negative_integer(value, field_name, errors)
        if total_tokens is not None:
            _validate_non_negative_integer(total_tokens, "total_tokens", errors)
        if errors:
            raise ModelValidationError(errors)
        resolved_total = input_tokens + output_tokens if total_tokens is None else total_tokens
        if resolved_total < input_tokens + output_tokens:
            errors.append("total_tokens must cover input_tokens and output_tokens")
        if errors:
            raise ModelValidationError(errors)
        self.model_calls += 1
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        self.reasoning_tokens += reasoning_tokens
        self.total_tokens += resolved_total
        self.latency_ms += latency_ms
        self.providers = sorted({*self.providers, provider.strip()})
        self.models = sorted({*self.models, model.strip()})
        self.validate()

    def merge(self, other: "UsageLedger") -> None:
        if not isinstance(other, UsageLedger):
            raise ModelValidationError(["usage ledger merge requires a UsageLedger"])
        self.validate()
        other.validate()
        self.model_calls += other.model_calls
        self.input_tokens += other.input_tokens
        self.output_tokens += other.output_tokens
        self.reasoning_tokens += other.reasoning_tokens
        self.total_tokens += other.total_tokens
        self.latency_ms += other.latency_ms
        self.providers = sorted({*self.providers, *other.providers})
        self.models = sorted({*self.models, *other.models})
        self.validate()

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: object) -> "UsageLedger":
        if not isinstance(payload, dict):
            raise ModelValidationError(["usage_ledger must be an object"])
        allowed = {
            "model_calls",
            "input_tokens",
            "output_tokens",
            "reasoning_tokens",
            "total_tokens",
            "latency_ms",
            "providers",
            "models",
        }
        unknown = set(payload) - allowed
        if unknown:
            raise ModelValidationError([f"usage_ledger contains unknown fields: {sorted(unknown)}"])
        ledger = cls(**payload)
        ledger.validate()
        return ledger
