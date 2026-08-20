"""Small explicit validators for model-produced structured data."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import math
from typing import Any


class ModelValidationError(ValueError):
    """Raised when structured model data violates its contract."""

    def __init__(self, errors: Sequence[str]) -> None:
        self.errors = tuple(errors)
        super().__init__("; ".join(self.errors))


def require_mapping(value: Any, field: str = "payload") -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ModelValidationError([f"{field} must be an object"])
    return value


def require_string(data: Mapping[str, Any], field: str, *, allow_empty: bool = False) -> str:
    value = data.get(field)
    if not isinstance(value, str):
        raise ModelValidationError([f"{field} must be a string"])
    value = value.strip()
    if not allow_empty and not value:
        raise ModelValidationError([f"{field} must not be empty"])
    return value


def optional_string(data: Mapping[str, Any], field: str) -> str | None:
    value = data.get(field)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ModelValidationError([f"{field} must be a string or null"])
    return value.strip() or None


def require_string_list(
    data: Mapping[str, Any], field: str, *, allow_empty: bool = True
) -> list[str]:
    value = data.get(field, [])
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ModelValidationError([f"{field} must be a list of strings"])
    result = [item.strip() for item in value if item.strip()]
    if not allow_empty and not result:
        raise ModelValidationError([f"{field} must not be empty"])
    return result


def require_choice(data: Mapping[str, Any], field: str, choices: set[str]) -> str:
    value = require_string(data, field)
    if value not in choices:
        allowed = ", ".join(sorted(choices))
        raise ModelValidationError([f"{field} must be one of: {allowed}"])
    return value


def require_boolean(data: Mapping[str, Any], field: str) -> bool:
    value = data.get(field)
    if not isinstance(value, bool):
        raise ModelValidationError([f"{field} must be a boolean"])
    return value


def require_integer(
    data: Mapping[str, Any], field: str, *, minimum: int | None = None
) -> int:
    value = data.get(field)
    if not isinstance(value, int) or isinstance(value, bool):
        raise ModelValidationError([f"{field} must be an integer"])
    if minimum is not None and value < minimum:
        raise ModelValidationError([f"{field} must be at least {minimum}"])
    return value


def require_number(data: Mapping[str, Any], field: str) -> float:
    value = data.get(field)
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
        raise ModelValidationError([f"{field} must be a finite number"])
    return float(value)


def require_dict(data: Mapping[str, Any], field: str) -> dict[str, Any]:
    value = data.get(field)
    if not isinstance(value, dict):
        raise ModelValidationError([f"{field} must be an object"])
    return value
