"""Workspace-bounded repository file ingestion and digest calculation."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from ..storage.workspace import WorkspacePaths, WorkspacePolicyError
from .chunkers import Chunker, LineChunker, MarkdownHeadingChunker, PythonAstChunker
from .models import RepositoryChunk


class IngestionError(ValueError):
    """Raised when repository ingestion configuration is invalid."""


@dataclass(slots=True, frozen=True)
class IngestedFile:
    path: str
    absolute_path: Path
    digest: str
    size: int
    modified_ns: int
    chunks: tuple[RepositoryChunk, ...]


class RepositoryIngestor:
    DEFAULT_SUFFIXES = frozenset(
        {".py", ".md", ".txt", ".json", ".toml", ".yaml", ".yml", ".js", ".ts", ".tsx", ".jsx", ".css", ".html"}
    )
    DEFAULT_IGNORED_DIRECTORIES = frozenset(
        {".git", ".coding-agent", ".tmp", "node_modules", "__pycache__", ".venv", "dist", "build", "coverage"}
    )

    def __init__(
        self,
        paths: WorkspacePaths,
        *,
        maximum_file_bytes: int = 1_000_000,
        suffixes: frozenset[str] = DEFAULT_SUFFIXES,
        ignored_directories: frozenset[str] = DEFAULT_IGNORED_DIRECTORIES,
    ) -> None:
        if maximum_file_bytes < 1:
            raise ValueError("maximum_file_bytes must be positive")
        self.paths = paths
        self.maximum_file_bytes = maximum_file_bytes
        self.suffixes = frozenset(item.lower() for item in suffixes)
        self.ignored_directories = ignored_directories
        self._text_chunker = LineChunker()
        self._python_chunker = PythonAstChunker(self._text_chunker)
        self._markdown_chunker = MarkdownHeadingChunker(self._text_chunker)

    def iter_files(self) -> list[Path]:
        files: list[Path] = []
        for candidate in self.paths.workspace_root.rglob("*"):
            relative = candidate.relative_to(self.paths.workspace_root)
            if any(part in self.ignored_directories for part in relative.parts):
                continue
            if not candidate.is_file() or candidate.suffix.lower() not in self.suffixes:
                continue
            try:
                if candidate.stat().st_size > self.maximum_file_bytes:
                    continue
            except OSError:
                continue
            try:
                resolved = self.paths.resolve_workspace_path(candidate, must_exist=True)
            except WorkspacePolicyError:
                continue
            if resolved.is_file():
                files.append(resolved)
        return sorted(set(files))

    def ingest(self, path: Path) -> IngestedFile:
        try:
            resolved = self.paths.resolve_workspace_path(path, must_exist=True)
            stat = resolved.stat()
        except (OSError, WorkspacePolicyError) as exc:
            raise IngestionError(f"cannot inspect repository file {path}: {exc}") from exc
        if not resolved.is_file() or resolved.suffix.lower() not in self.suffixes:
            raise IngestionError(f"file is not an ingestible text source: {path}")
        if stat.st_size > self.maximum_file_bytes:
            raise IngestionError(f"file exceeds ingestion size limit: {path}")
        try:
            raw = resolved.read_bytes()
            source = raw.decode("utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            raise IngestionError(f"cannot decode repository file {path}: {exc}") from exc
        digest = hashlib.sha256(raw).hexdigest()
        relative = str(resolved.relative_to(self.paths.workspace_root))
        chunker = self._python_chunker if resolved.suffix.lower() == ".py" else (
            self._markdown_chunker if resolved.suffix.lower() in {".md", ".markdown"} else self._text_chunker
        )
        chunks = tuple(chunker.chunk(relative, source, digest))
        return IngestedFile(relative, resolved, digest, stat.st_size, stat.st_mtime_ns, chunks)
