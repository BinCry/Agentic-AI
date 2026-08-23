"""Crash-aware bounded observations and tool-call idempotency records."""

from __future__ import annotations

import hashlib
import json
import math
import os
from contextlib import suppress
from dataclasses import replace
from pathlib import Path
from typing import Any
from uuid import uuid4

from ..models.observation import (
    DIGEST_PATTERN,
    IDEMPOTENCY_KEY_PATTERN,
    OBSERVATION_ID_PATTERN,
    ObservationConflictError,
    ObservationQuotaError,
    ObservationRecord,
    ObservationStoreError,
)
from ..models.task_state import TASK_ID_PATTERN, utc_now
from ..observability.trace import redact_text
from .workspace import WorkspacePaths, WorkspacePolicyError


class ObservationStore:
    def __init__(
        self,
        paths: WorkspacePaths,
        *,
        maximum_item_bytes: int = 524_288,
        maximum_session_bytes: int = 8_388_608,
        maximum_observations: int = 1_000,
        maximum_summary_chars: int = 4_000,
    ) -> None:
        limits = (
            maximum_item_bytes,
            maximum_session_bytes,
            maximum_observations,
            maximum_summary_chars,
        )
        if any(not isinstance(value, int) or isinstance(value, bool) or value < 1 for value in limits):
            raise ValueError("observation limits must be positive integers")
        if maximum_item_bytes > maximum_session_bytes:
            raise ValueError("item limit cannot exceed session limit")
        self.paths = paths.ensure()
        self.maximum_item_bytes = maximum_item_bytes
        self.maximum_session_bytes = maximum_session_bytes
        self.maximum_observations = maximum_observations
        self.maximum_summary_chars = maximum_summary_chars

    def reserve(
        self,
        task_id: str,
        idempotency_key: str,
        tool_name: str,
        request_sha256: str,
    ) -> ObservationRecord:
        record, _ = self.claim(
            task_id, idempotency_key, tool_name, request_sha256
        )
        return record

    def claim(
        self,
        task_id: str,
        idempotency_key: str,
        tool_name: str,
        request_sha256: str,
    ) -> tuple[ObservationRecord, bool]:
        """Reserve a call and report whether this caller owns the new claim."""
        self._validate_identity(task_id, idempotency_key, request_sha256)
        if not isinstance(tool_name, str) or not tool_name.strip() or len(tool_name) > 128:
            raise ObservationStoreError("tool_name is invalid")
        existing = self.find_by_idempotency_key(task_id, idempotency_key)
        if existing is not None:
            if existing.request_sha256 != request_sha256 or existing.tool_name != tool_name:
                raise ObservationConflictError("idempotency key is bound to another request")
            return existing, False
        records = self.list(task_id)
        if len(records) >= self.maximum_observations:
            raise ObservationQuotaError("observation count limit exceeded")
        digest = hashlib.sha256(f"{task_id}\0{idempotency_key}".encode()).hexdigest()[:32]
        record = ObservationRecord(
            f"observation-{digest}",
            task_id,
            idempotency_key,
            tool_name.strip(),
            request_sha256,
            "pending",
            "",
            None,
            None,
            0,
            False,
            utc_now(),
        )
        record.validate()
        self._write_index(task_id, [*records, record])
        return record, True

    def complete(
        self,
        record: ObservationRecord,
        result: dict[str, Any],
        *,
        summary: str,
        truncated: bool = False,
    ) -> ObservationRecord:
        record.validate()
        current = self.find_by_idempotency_key(record.task_id, record.idempotency_key)
        if current is None or current.observation_id != record.observation_id:
            raise ObservationStoreError("observation reservation is missing")
        if current.status == "completed":
            return current
        raw = self._encode_result(result)
        if len(raw) > self.maximum_item_bytes:
            raise ObservationQuotaError("observation item byte limit exceeded")
        existing_bytes = sum(item.result_bytes for item in self.list(record.task_id))
        if existing_bytes + len(raw) > self.maximum_session_bytes:
            raise ObservationQuotaError("observation session byte limit exceeded")
        artifact = self._artifact_path(current)
        relative = str(artifact.relative_to(self.paths.workspace_root)).replace("\\", "/")
        completed = replace(
            current,
            status="completed",
            summary=redact_text(summary)[: self.maximum_summary_chars],
            result_sha256=hashlib.sha256(raw).hexdigest(),
            artifact_path=relative,
            result_bytes=len(raw),
            truncated=truncated,
            completed_at=utc_now(),
        )
        completed.validate()
        self._atomic_write(artifact, {"record": completed.to_dict(), "result": result})
        records = [
            completed if item.observation_id == completed.observation_id else item
            for item in self.list(record.task_id)
        ]
        self._write_index(record.task_id, records)
        return completed

    def append(
        self,
        task_id: str,
        idempotency_key: str,
        tool_name: str,
        request_sha256: str,
        result: dict[str, Any],
        *,
        summary: str,
        truncated: bool = False,
    ) -> ObservationRecord:
        reserved = self.reserve(task_id, idempotency_key, tool_name, request_sha256)
        return self.complete(reserved, result, summary=summary, truncated=truncated)

    def find_by_idempotency_key(
        self, task_id: str, idempotency_key: str
    ) -> ObservationRecord | None:
        self._validate_identity(task_id, idempotency_key, "0" * 64)
        return next((item for item in self.list(task_id) if item.idempotency_key == idempotency_key), None)

    def get(self, task_id: str, observation_id: str) -> ObservationRecord:
        if not isinstance(observation_id, str) or not OBSERVATION_ID_PATTERN.fullmatch(
            observation_id
        ):
            raise ObservationStoreError("observation_id is invalid")
        record = next((item for item in self.list(task_id) if item.observation_id == observation_id), None)
        if record is None:
            raise FileNotFoundError(observation_id)
        return record

    def get_result(self, record: ObservationRecord) -> dict[str, Any]:
        record.validate()
        if record.status != "completed" or record.artifact_path is None:
            raise ObservationStoreError("observation has no completed result")
        _, result = self._read_artifact(record, use_record_path=True)
        return result

    def list(self, task_id: str) -> list[ObservationRecord]:
        if not TASK_ID_PATTERN.fullmatch(task_id):
            raise ObservationStoreError("task_id is invalid")
        target = self._index_path(task_id)
        if not target.is_file():
            return []
        payload = self._load_json(target)
        if not isinstance(payload, list):
            raise ObservationStoreError("observation index must contain a list")
        records = [ObservationRecord.from_dict(item) for item in payload]
        if any(item.task_id != task_id for item in records):
            raise ObservationStoreError("observation task identity mismatch")
        keys = [item.idempotency_key for item in records]
        if len(keys) != len(set(keys)):
            raise ObservationStoreError("observation index contains duplicate idempotency keys")
        reconciled: list[ObservationRecord] = []
        changed = False
        for record in records:
            if record.status == "pending" and self._artifact_path(record).is_file():
                completed, _ = self._read_artifact(record, use_record_path=False)
                reconciled.append(completed)
                changed = True
            else:
                reconciled.append(record)
        if changed:
            self._write_index(task_id, reconciled)
        return reconciled

    def _read_artifact(
        self, record: ObservationRecord, *, use_record_path: bool
    ) -> tuple[ObservationRecord, dict[str, Any]]:
        try:
            if use_record_path:
                if record.artifact_path is None:
                    raise ObservationStoreError("observation artifact path is missing")
                artifact = self.paths.resolve_workspace_path(
                    record.artifact_path, must_exist=True
                )
                if not artifact.is_relative_to(self.paths.runtime_root):
                    raise ObservationStoreError(
                        "observation artifact escapes runtime root"
                    )
            else:
                artifact = self._artifact_path(record)
        except WorkspacePolicyError as exc:
            raise ObservationStoreError("observation artifact path is invalid") from exc
        payload = self._load_json(artifact)
        if not isinstance(payload, dict) or set(payload) != {"record", "result"}:
            raise ObservationStoreError("observation artifact shape is invalid")
        completed = ObservationRecord.from_dict(payload["record"])
        expected_path = str(artifact.relative_to(self.paths.workspace_root)).replace(
            "\\", "/"
        )
        if (
            completed.status != "completed"
            or completed.observation_id != record.observation_id
            or completed.task_id != record.task_id
            or completed.idempotency_key != record.idempotency_key
            or completed.tool_name != record.tool_name
            or completed.request_sha256 != record.request_sha256
            or completed.created_at != record.created_at
            or completed.artifact_path != expected_path
        ):
            raise ObservationStoreError("observation artifact identity mismatch")
        result = payload["result"]
        raw = self._encode_result(result)
        if (
            hashlib.sha256(raw).hexdigest() != completed.result_sha256
            or len(raw) != completed.result_bytes
        ):
            raise ObservationStoreError("observation result digest mismatch")
        return completed, result

    def _write_index(self, task_id: str, records: list[ObservationRecord]) -> None:
        self._atomic_write(self._index_path(task_id), [item.to_dict() for item in records])

    def _index_path(self, task_id: str) -> Path:
        return self.paths.resolve_runtime_path(Path("observations") / task_id / "index.json")

    def _artifact_path(self, record: ObservationRecord) -> Path:
        return self.paths.resolve_runtime_path(
            Path("observations") / record.task_id / f"{record.observation_id}.json"
        )

    @staticmethod
    def _validate_identity(task_id: str, key: str, request_sha256: str) -> None:
        if not isinstance(task_id, str) or not TASK_ID_PATTERN.fullmatch(task_id):
            raise ObservationStoreError("task_id is invalid")
        if not isinstance(key, str) or not IDEMPOTENCY_KEY_PATTERN.fullmatch(key):
            raise ObservationStoreError("idempotency_key is invalid")
        if not isinstance(request_sha256, str) or not DIGEST_PATTERN.fullmatch(
            request_sha256
        ):
            raise ObservationStoreError("request_sha256 is invalid")

    @staticmethod
    def _encode_result(result: object) -> bytes:
        if not isinstance(result, dict) or not _is_canonical_json(result):
            raise ObservationStoreError(
                "observation result must contain canonical finite JSON"
            )
        try:
            return json.dumps(
                result,
                ensure_ascii=False,
                allow_nan=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        except (TypeError, ValueError) as exc:
            raise ObservationStoreError(
                "observation result must contain canonical finite JSON"
            ) from exc

    @staticmethod
    def _load_json(target: Path) -> object:
        try:
            with target.open("r", encoding="utf-8") as handle:
                return json.load(handle)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ObservationStoreError(f"observation file is invalid: {target.name}") from exc

    @staticmethod
    def _atomic_write(target: Path, payload: object) -> None:
        temporary = target.with_name(f".{target.name}.{os.getpid()}.{uuid4().hex}.tmp")
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            with temporary.open("x", encoding="utf-8", newline="\n") as handle:
                json.dump(payload, handle, ensure_ascii=False, allow_nan=False, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, target)
        except (OSError, TypeError, ValueError) as exc:
            raise ObservationStoreError(
                f"observation write failed: {target.name}"
            ) from exc
        finally:
            with suppress(OSError):
                temporary.unlink(missing_ok=True)


def _is_canonical_json(value: object) -> bool:
    if value is None or isinstance(value, (str, bool, int)):
        return True
    if isinstance(value, float):
        return math.isfinite(value)
    if isinstance(value, list):
        return all(_is_canonical_json(item) for item in value)
    if isinstance(value, dict):
        return all(
            isinstance(key, str)
            and bool(key)
            and _is_canonical_json(item)
            for key, item in value.items()
        )
    return False
