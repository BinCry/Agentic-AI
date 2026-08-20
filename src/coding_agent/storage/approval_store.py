"""Crash-safe ledger for high-risk tool approval decisions."""

from __future__ import annotations

import json
import os
from dataclasses import asdict
from pathlib import Path
from uuid import uuid4

from ..models.records import ApprovalDecisionRecord
from ..storage.workspace import WorkspacePaths


class ApprovalLedger:
    """Persist approval decisions independently from the mutable task snapshot."""

    def __init__(self, paths: WorkspacePaths) -> None:
        self.paths = paths.ensure()

    def append(self, record: ApprovalDecisionRecord) -> Path:
        target = self.paths.resolve_runtime_path(
            Path("approvals") / f"{record.task_id}.json", must_exist=False
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        records = self.load(record.task_id)
        records.append(record)
        payload = [asdict(item) for item in records]
        self._atomic_write(target, payload)
        return target

    def load(self, task_id: str) -> list[ApprovalDecisionRecord]:
        target = self.paths.resolve_runtime_path(
            Path("approvals") / f"{task_id}.json", must_exist=False
        )
        if not target.is_file():
            return []
        with target.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if not isinstance(payload, list):
            raise ValueError("approval ledger must contain a list")
        return [ApprovalDecisionRecord.from_dict(item) for item in payload]

    @staticmethod
    def _atomic_write(target: Path, payload: object) -> None:
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
            raise RuntimeError("unable to allocate approval-ledger temporary file")
        try:
            with handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)
