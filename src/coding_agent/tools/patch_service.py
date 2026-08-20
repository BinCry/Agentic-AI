"""Conflict-aware, single-file unified patch and create operations."""

from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path

from ..models.records import PatchRecord
from ..models.task_state import utc_now
from ..storage.workspace import WorkspacePaths, WorkspacePolicyError


class PatchToolError(ValueError):
    """Raised when a patch or file creation is unsafe or cannot be applied."""


class PatchConflictError(PatchToolError):
    """Raised when the expected source content no longer matches."""


HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


class PatchService:
    def __init__(self, paths: WorkspacePaths, *, maximum_patch_bytes: int = 1_000_000) -> None:
        self.paths = paths
        self.maximum_patch_bytes = maximum_patch_bytes

    def create_file(self, path: str, content: str) -> PatchRecord:
        target = self._new_file_path(path)
        if len(content.encode("utf-8")) > self.maximum_patch_bytes:
            raise PatchToolError("file content exceeds patch-size policy")
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            with target.open("x", encoding="utf-8", newline="") as handle:
                handle.write(content)
        except FileExistsError as exc:
            raise PatchConflictError(f"file already exists: {path}") from exc
        except OSError as exc:
            raise PatchToolError(f"cannot create file {path}: {exc}") from exc
        return PatchRecord(path, content, True, utc_now())

    def apply_unified_patch(
        self,
        path: str,
        patch: str,
        *,
        expected_sha256: str,
    ) -> PatchRecord:
        target = self._existing_file_path(path)
        if len(patch.encode("utf-8")) > self.maximum_patch_bytes:
            raise PatchToolError("patch exceeds patch-size policy")
        original = target.read_text(encoding="utf-8")
        actual_sha256 = hashlib.sha256(original.encode("utf-8")).hexdigest()
        if actual_sha256.lower() != expected_sha256.lower():
            raise PatchConflictError(f"source digest mismatch for {path}")
        updated = self._apply_hunks(original, patch, path)
        if updated == original:
            raise PatchToolError("patch does not change the file")
        self._atomic_replace(target, updated)
        return PatchRecord(path, patch, True, utc_now())

    def _apply_hunks(self, original: str, patch: str, path: str) -> str:
        source_lines = original.splitlines(keepends=True)
        patch_lines = patch.splitlines(keepends=True)
        hunks = [
            (index, match)
            for index, line in enumerate(patch_lines)
            if (match := HUNK_RE.match(line.rstrip("\r\n")))
        ]
        if not hunks:
            raise PatchToolError(f"patch has no unified-diff hunks: {path}")
        output: list[str] = []
        source_index = 0
        for hunk_position, (hunk_index, match) in enumerate(hunks):
            old_start = int(match.group(1))
            old_count = int(match.group(2) or "1")
            hunk_end = hunks[hunk_position + 1][0] if hunk_position + 1 < len(hunks) else len(patch_lines)
            expected_index = old_start - 1
            if expected_index < source_index or expected_index > len(source_lines):
                raise PatchConflictError(f"patch hunk starts outside current file: {path}")
            output.extend(source_lines[source_index:expected_index])
            consumed = 0
            for line in patch_lines[hunk_index + 1 : hunk_end]:
                if line.startswith("\\ No newline"):
                    continue
                if not line:
                    raise PatchToolError("malformed empty patch line")
                marker, content = line[0], line[1:]
                if marker == " ":
                    if source_index + consumed >= len(source_lines) or source_lines[source_index + consumed] != content:
                        raise PatchConflictError(f"patch context mismatch in {path}")
                    output.append(content)
                    consumed += 1
                elif marker == "-":
                    if source_index + consumed >= len(source_lines) or source_lines[source_index + consumed] != content:
                        raise PatchConflictError(f"patch deletion mismatch in {path}")
                    consumed += 1
                elif marker == "+":
                    output.append(content)
                else:
                    raise PatchToolError(f"malformed patch line in {path}")
            if consumed != old_count:
                raise PatchToolError(f"patch hunk line count mismatch in {path}")
            source_index += consumed
        output.extend(source_lines[source_index:])
        return "".join(output)

    def _existing_file_path(self, path: str) -> Path:
        try:
            target = self.paths.resolve_workspace_path(path, must_exist=True)
        except WorkspacePolicyError as exc:
            raise PatchToolError(str(exc)) from exc
        if not target.is_file():
            raise PatchToolError(f"path is not a file: {path}")
        return target

    def _new_file_path(self, path: str) -> Path:
        try:
            target = self.paths.resolve_workspace_path(path)
            self.paths.resolve_workspace_path(target.parent, must_exist=True)
        except WorkspacePolicyError as exc:
            raise PatchToolError(str(exc)) from exc
        if target.exists():
            raise PatchConflictError(f"file already exists: {path}")
        return target

    @staticmethod
    def _atomic_replace(target: Path, content: str) -> None:
        temporary = target.with_name(f".{target.name}.{os.getpid()}.patch.tmp")
        try:
            with temporary.open("x", encoding="utf-8", newline="") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, target)
        except OSError as exc:
            temporary.unlink(missing_ok=True)
            raise PatchToolError(f"cannot atomically replace {target}: {exc}") from exc
