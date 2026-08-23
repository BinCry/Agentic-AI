"""Atomic task checkpoints and deterministic rollback recovery."""

from __future__ import annotations

import json
import os
import re
import base64
from dataclasses import asdict
from pathlib import Path
from uuid import uuid4

from ..models.records import CheckpointRecord
from ..models.task_state import CodingTaskState, utc_now
from .workspace import WorkspacePaths
from .task_state_migrations import TaskStateMigrator


CHECKPOINT_ID_PATTERN = re.compile(r"^checkpoint-[0-9]{4,}-[0-9]{4,}$")


class CheckpointNotFoundError(FileNotFoundError):
    """Raised when a requested checkpoint does not exist."""


class CheckpointStore:
    """Store immutable, workspace-contained snapshots before risky operations."""

    def __init__(self, paths: WorkspacePaths) -> None:
        self.paths = paths.ensure()
        self.migrator = TaskStateMigrator()

    def create(
        self,
        state: CodingTaskState,
        reason: str,
        *,
        file_paths: tuple[str, ...] = (),
    ) -> CheckpointRecord:
        if not reason.strip():
            raise ValueError("checkpoint reason must not be empty")
        state.validate()
        sequence = len(state.checkpoints) + 1
        checkpoint_id = f"checkpoint-{state.current_iteration:04d}-{sequence:04d}"
        target = self._path(state.task_id, checkpoint_id)
        while target.exists():
            sequence += 1
            checkpoint_id = f"checkpoint-{state.current_iteration:04d}-{sequence:04d}"
            target = self._path(state.task_id, checkpoint_id)
        record = CheckpointRecord(
            checkpoint_id=checkpoint_id,
            workflow_state=state.current_status.value,
            state_path=self._relative_path(target),
            created_at=utc_now(),
            reason=reason.strip(),
        )
        state_payload = state.to_dict()
        state_payload["checkpoints"] = [*state_payload.get("checkpoints", []), asdict(record)]
        files: dict[str, str | None] = {}
        for value in file_paths:
            resolved = self.paths.resolve_workspace_path(value)
            relative = str(resolved.relative_to(self.paths.workspace_root)).replace("\\", "/")
            files[relative] = (
                base64.b64encode(resolved.read_bytes()).decode("ascii") if resolved.is_file() else None
            )
        self._atomic_write(target, {"state": state_payload, "files": files})
        state.checkpoints.append(record)
        state.touch()
        state.validate()
        return record

    def restore(self, task_id: str, checkpoint_id: str | None = None) -> CodingTaskState:
        target = self._path(task_id, checkpoint_id or self._latest_id(task_id))
        if not target.is_file():
            raise CheckpointNotFoundError(str(target))
        with target.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        state_payload = payload.get("state", payload)
        state = CodingTaskState.from_dict(self.migrator.migrate(state_payload))
        if state.task_id != task_id:
            raise ValueError("checkpoint task identity does not match requested task")
        self._restore_files(payload.get("files", {}))
        return state

    def list_records(self, task_id: str) -> tuple[CheckpointRecord, ...]:
        records: list[CheckpointRecord] = []
        for target in self._directory(task_id).glob("checkpoint-*.json"):
            if not target.is_file():
                continue
            with target.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
            state = CodingTaskState.from_dict(
                self.migrator.migrate(payload.get("state", payload))
            )
            if state.checkpoints:
                records.append(state.checkpoints[-1])
        return tuple(sorted(records, key=lambda item: item.checkpoint_id))

    def _latest_id(self, task_id: str) -> str:
        records = self.list_records(task_id)
        if not records:
            raise CheckpointNotFoundError(task_id)
        return records[-1].checkpoint_id

    def _directory(self, task_id: str) -> Path:
        return self.paths.resolve_runtime_path(Path("checkpoints") / task_id)

    def _path(self, task_id: str, checkpoint_id: str) -> Path:
        if not CHECKPOINT_ID_PATTERN.fullmatch(checkpoint_id):
            raise ValueError("checkpoint id is invalid")
        return self.paths.resolve_runtime_path(
            Path("checkpoints") / task_id / f"{checkpoint_id}.json"
        )

    def _relative_path(self, path: Path) -> str:
        return str(path.relative_to(self.paths.workspace_root)).replace("\\", "/")

    def _restore_files(self, snapshots: object) -> None:
        if not isinstance(snapshots, dict):
            raise ValueError("checkpoint file snapshots must be an object")
        for value, encoded in snapshots.items():
            if not isinstance(value, str) or (encoded is not None and not isinstance(encoded, str)):
                raise ValueError("checkpoint file snapshot is malformed")
            target = self.paths.resolve_workspace_path(value)
            if encoded is None:
                if target.exists() and target.is_file():
                    target.unlink()
                continue
            try:
                content = base64.b64decode(encoded, validate=True)
            except (ValueError, TypeError) as exc:
                raise ValueError("checkpoint file snapshot is not valid base64") from exc
            self._atomic_write_bytes(target, content)

    @staticmethod
    def _atomic_write_bytes(target: Path, content: bytes) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(f".{target.name}.{os.getpid()}.{uuid4().hex}.rollback.tmp")
        try:
            with temporary.open("xb") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)

    @staticmethod
    def _atomic_write(target: Path, payload: object) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        handle = None
        for _ in range(10):
            candidate = target.with_suffix(f".json.{os.getpid()}.{uuid4().hex}.tmp")
            try:
                handle = candidate.open("x", encoding="utf-8", newline="\n")
                temporary = candidate
                break
            except FileExistsError:
                continue
        if temporary is None or handle is None:
            raise RuntimeError("unable to allocate checkpoint temporary file")
        try:
            with handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)
