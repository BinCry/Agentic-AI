"""Bounded root-to-leaf discovery for untrusted repository instructions."""

from __future__ import annotations

import hashlib
from dataclasses import replace
from pathlib import Path
from typing import Iterable

from ..storage.workspace import WorkspacePaths
from .profile import InstructionBlock, ProjectProfile


class InstructionResolver:
    """Read scoped instruction data while retaining source provenance."""

    names = ("CLAUDE.md", "AGENTS.md")

    def __init__(
        self,
        paths: WorkspacePaths,
        *,
        maximum_files: int = 16,
        maximum_file_bytes: int = 16_384,
        maximum_total_bytes: int = 65_536,
        maximum_source_bytes: int = 1_048_576,
    ) -> None:
        limits = (maximum_files, maximum_file_bytes, maximum_total_bytes, maximum_source_bytes)
        if any(not isinstance(value, int) or isinstance(value, bool) or value < 1 for value in limits):
            raise ValueError("instruction limits must be positive integers")
        self.paths = paths.ensure()
        self.maximum_files = maximum_files
        self.maximum_file_bytes = maximum_file_bytes
        self.maximum_total_bytes = maximum_total_bytes
        self.maximum_source_bytes = maximum_source_bytes

    def resolve(self, relative_target: str | None = None) -> tuple[InstructionBlock, ...]:
        scopes = self._scopes(relative_target)
        blocks: list[InstructionBlock] = []
        total_bytes = 0
        for scope in scopes:
            for name in self.names:
                candidate = scope / name
                if not candidate.exists() and not candidate.is_symlink():
                    continue
                resolved = self.paths.resolve_workspace_path(candidate, must_exist=True)
                if not resolved.is_file() or resolved.stat().st_size > self.maximum_source_bytes:
                    continue
                raw = resolved.read_bytes()
                if b"\x00" in raw:
                    continue
                try:
                    raw.decode("utf-8")
                except UnicodeDecodeError:
                    continue
                remaining = self.maximum_total_bytes - total_bytes
                if remaining < 1 or len(blocks) >= self.maximum_files:
                    return tuple(blocks)
                allowed = min(self.maximum_file_bytes, remaining)
                selected = raw[:allowed]
                content = selected.decode("utf-8", errors="ignore")
                block_path = candidate.relative_to(self.paths.workspace_root).as_posix()
                scope_path = scope.relative_to(self.paths.workspace_root).as_posix() or "."
                blocks.append(
                    InstructionBlock(
                        block_path,
                        scope_path,
                        hashlib.sha256(raw).hexdigest(),
                        content,
                        truncated=len(raw) > len(selected),
                    )
                )
                total_bytes += len(selected)
        return tuple(blocks)

    def _scopes(self, relative_target: str | None) -> tuple[Path, ...]:
        target = self.paths.resolve_workspace_path(relative_target or ".")
        scope = target.parent if target.exists() and target.is_file() else target
        if not target.exists() and target.suffix:
            scope = target.parent
        relative = scope.relative_to(self.paths.workspace_root)
        scopes = [self.paths.workspace_root]
        current = self.paths.workspace_root
        for part in relative.parts:
            current /= part
            scopes.append(current)
        return tuple(scopes)


def merge_scoped_instructions(
    profile: ProjectProfile,
    resolver: InstructionResolver,
    targets: Iterable[str],
) -> ProjectProfile:
    """Return a profile containing deterministic instructions for observed targets."""
    blocks = {item.path: item for item in profile.instructions}
    for target in sorted(set(targets)):
        for block in resolver.resolve(target):
            blocks[block.path] = block
    ordered = sorted(
        blocks.values(),
        key=lambda item: (
            0 if item.scope == "." else len(Path(item.scope).parts),
            item.scope,
            0 if Path(item.path).name == "CLAUDE.md" else 1,
            item.path,
        ),
    )
    return replace(profile, instructions=tuple(ordered))
