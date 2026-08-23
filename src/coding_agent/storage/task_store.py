"""Atomic JSON persistence for CodingTaskState."""

from __future__ import annotations

import json
import os
from pathlib import Path
from uuid import uuid4

from ..models.task_state import TASK_ID_PATTERN, CodingTaskState
from ..models.task_state_schema import CURRENT_TASK_SCHEMA_VERSION
from .task_state_migrations import TaskStateMigrationError, TaskStateMigrator
from .workspace import WorkspacePaths


class TaskNotFoundError(FileNotFoundError):
    """Raised when a requested task state is absent."""


class JsonTaskStore:
    def __init__(self, paths: WorkspacePaths) -> None:
        self.paths = paths
        self.migrator = TaskStateMigrator()

    def save(self, state: CodingTaskState) -> Path:
        state.validate()
        state.touch()
        target = self.paths.task_path(state.task_id)
        target.parent.mkdir(parents=True, exist_ok=True)
        self._backup_legacy_state(target, state.task_id)
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
            raise RuntimeError("unable to allocate an exclusive task-state temporary file")
        try:
            with handle:
                json.dump(state.to_dict(), handle, ensure_ascii=False, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)
        return target

    def load(self, task_id: str) -> CodingTaskState:
        self._validate_task_id(task_id)
        target = self.paths.task_path(task_id)
        if not target.is_file():
            raise TaskNotFoundError(task_id)
        with target.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        return CodingTaskState.from_dict(self.migrator.migrate(payload))

    def list_task_ids(self) -> tuple[str, ...]:
        task_dir = self.paths.resolve_runtime_path("tasks")
        if not task_dir.is_dir():
            return ()
        return tuple(sorted(path.stem for path in task_dir.glob("*.json") if path.is_file()))

    @staticmethod
    def _validate_task_id(task_id: str) -> None:
        if not TASK_ID_PATTERN.fullmatch(task_id):
            raise ValueError("task_id contains unsafe characters")

    def _backup_legacy_state(self, target: Path, task_id: str) -> None:
        if not target.is_file():
            return
        content = target.read_bytes()
        try:
            payload = json.loads(content)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise TaskStateMigrationError("existing task state is not valid UTF-8 JSON") from exc
        version = self.migrator.version_of(payload)
        if version == CURRENT_TASK_SCHEMA_VERSION:
            return
        backup = self.paths.resolve_runtime_path(
            Path("task-backups") / f"{task_id}.v{version}.json"
        )
        backup.parent.mkdir(parents=True, exist_ok=True)
        if backup.exists():
            if backup.read_bytes() != content:
                raise TaskStateMigrationError("existing legacy task-state backup differs")
            return
        temporary = backup.with_name(f".{backup.name}.{os.getpid()}.{uuid4().hex}.tmp")
        try:
            with temporary.open("xb") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            try:
                if os.name == "nt":
                    os.rename(temporary, backup)
                else:
                    os.link(temporary, backup)
            except FileExistsError:
                if backup.read_bytes() != content:
                    raise TaskStateMigrationError("concurrent legacy task-state backup differs")
        finally:
            temporary.unlink(missing_ok=True)
