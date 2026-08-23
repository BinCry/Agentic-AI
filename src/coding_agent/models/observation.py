"""Typed durable observation contracts."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any

from .task_state import TASK_ID_PATTERN


IDEMPOTENCY_KEY_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}")
DIGEST_PATTERN = re.compile(r"[0-9a-f]{64}")
OBSERVATION_ID_PATTERN = re.compile(r"observation-[0-9a-f]{32}")


class ObservationStoreError(ValueError):
    """Raised when an observation ledger or artifact violates its contract."""


class ObservationConflictError(ObservationStoreError):
    """Raised when an idempotency key is reused for a different request."""


class ObservationQuotaError(ObservationStoreError):
    """Raised before persistence when item or session limits are exceeded."""


@dataclass(slots=True, frozen=True)
class ObservationRecord:
    observation_id: str
    task_id: str
    idempotency_key: str
    tool_name: str
    request_sha256: str
    status: str
    summary: str
    result_sha256: str | None
    artifact_path: str | None
    result_bytes: int
    truncated: bool
    created_at: str
    completed_at: str | None = None

    @classmethod
    def from_dict(cls, payload: object) -> "ObservationRecord":
        if not isinstance(payload, dict):
            raise ObservationStoreError("observation record must be an object")
        allowed = set(cls.__dataclass_fields__)
        unknown = set(payload) - allowed
        if unknown:
            raise ObservationStoreError(
                f"observation contains unknown fields: {sorted(unknown)}"
            )
        try:
            record = cls(**payload)
        except TypeError as exc:
            raise ObservationStoreError(
                "observation record fields are incomplete"
            ) from exc
        record.validate()
        return record

    def validate(self) -> None:
        if not isinstance(self.observation_id, str) or not OBSERVATION_ID_PATTERN.fullmatch(
            self.observation_id
        ):
            raise ObservationStoreError("observation_id is invalid")
        if not isinstance(self.task_id, str) or not TASK_ID_PATTERN.fullmatch(self.task_id):
            raise ObservationStoreError("task_id is invalid")
        if not isinstance(
            self.idempotency_key, str
        ) or not IDEMPOTENCY_KEY_PATTERN.fullmatch(self.idempotency_key):
            raise ObservationStoreError("idempotency_key is invalid")
        if (
            not isinstance(self.tool_name, str)
            or not self.tool_name.strip()
            or len(self.tool_name) > 128
        ):
            raise ObservationStoreError("tool_name is invalid")
        if not isinstance(self.request_sha256, str) or not DIGEST_PATTERN.fullmatch(
            self.request_sha256
        ):
            raise ObservationStoreError("request_sha256 is invalid")
        if self.status not in {"pending", "completed"}:
            raise ObservationStoreError("observation status is invalid")
        if not isinstance(self.summary, str) or not isinstance(self.truncated, bool):
            raise ObservationStoreError(
                "observation summary/truncated fields are invalid"
            )
        if (
            not isinstance(self.result_bytes, int)
            or isinstance(self.result_bytes, bool)
            or self.result_bytes < 0
        ):
            raise ObservationStoreError("result_bytes is invalid")
        if not isinstance(self.created_at, str) or not self.created_at:
            raise ObservationStoreError("created_at is invalid")
        completed_values = (
            self.result_sha256,
            self.artifact_path,
            self.completed_at,
        )
        if self.status == "pending":
            if any(value is not None for value in completed_values) or self.result_bytes:
                raise ObservationStoreError(
                    "pending observation contains completed result fields"
                )
        elif (
            not isinstance(self.result_sha256, str)
            or not DIGEST_PATTERN.fullmatch(self.result_sha256)
            or not isinstance(self.artifact_path, str)
            or not self.artifact_path
            or not isinstance(self.completed_at, str)
            or not self.completed_at
        ):
            raise ObservationStoreError(
                "completed observation is missing result fields"
            )

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return asdict(self)
