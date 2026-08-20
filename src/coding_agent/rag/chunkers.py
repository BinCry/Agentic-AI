"""Code-aware and heading-aware chunkers with exact source line ranges."""

from __future__ import annotations

import ast
import re
from typing import Protocol

from .models import RepositoryChunk


class Chunker(Protocol):
    def chunk(self, path: str, source: str, file_digest: str) -> list[RepositoryChunk]: ...


class LineChunker:
    def __init__(self, *, maximum_lines: int = 80, overlap_lines: int = 10) -> None:
        if maximum_lines < 1 or overlap_lines < 0 or overlap_lines >= maximum_lines:
            raise ValueError("invalid line chunk limits")
        self.maximum_lines = maximum_lines
        self.overlap_lines = overlap_lines

    def chunk(self, path: str, source: str, file_digest: str) -> list[RepositoryChunk]:
        lines = source.splitlines(keepends=True)
        if not lines:
            return []
        chunks: list[RepositoryChunk] = []
        start = 0
        while start < len(lines):
            end = min(start + self.maximum_lines, len(lines))
            chunks.append(
                RepositoryChunk.create(
                    path,
                    start + 1,
                    end,
                    "".join(lines[start:end]),
                    kind="text",
                    symbol=None,
                    file_digest=file_digest,
                )
            )
            if end == len(lines):
                break
            start = end - self.overlap_lines
        return chunks


class PythonAstChunker:
    def __init__(self, fallback: LineChunker | None = None) -> None:
        self.fallback = fallback or LineChunker()

    def chunk(self, path: str, source: str, file_digest: str) -> list[RepositoryChunk]:
        lines = source.splitlines(keepends=True)
        try:
            tree = ast.parse(source, filename=path)
        except SyntaxError:
            return self.fallback.chunk(path, source, file_digest)
        chunks: list[RepositoryChunk] = []

        def visit(body: list[ast.stmt], prefix: str = "") -> None:
            for node in body:
                if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                    name = f"{prefix}.{node.name}" if prefix else node.name
                    start = max(1, node.lineno)
                    end = getattr(node, "end_lineno", start)
                    chunks.append(
                        RepositoryChunk.create(
                            path,
                            start,
                            end,
                            "".join(lines[start - 1 : end]),
                            kind="python-symbol",
                            symbol=name,
                            file_digest=file_digest,
                        )
                    )
                    nested = getattr(node, "body", None)
                    if isinstance(nested, list):
                        visit(nested, name)

        visit(tree.body)
        if not chunks:
            return self.fallback.chunk(path, source, file_digest)
        return chunks


class MarkdownHeadingChunker:
    HEADING_RE = re.compile(r"^(#{1,6})[ \t]+(.+?)\s*$")

    def __init__(self, fallback: LineChunker | None = None) -> None:
        self.fallback = fallback or LineChunker()

    def chunk(self, path: str, source: str, file_digest: str) -> list[RepositoryChunk]:
        lines = source.splitlines(keepends=True)
        headings: list[tuple[int, int, str]] = []
        fenced = False
        for index, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("```") or stripped.startswith("~~~"):
                fenced = not fenced
                continue
            if fenced:
                continue
            match = self.HEADING_RE.match(line.rstrip("\r\n"))
            if match:
                headings.append((index, len(match.group(1)), match.group(2).strip()))
        if not headings:
            return self.fallback.chunk(path, source, file_digest)
        chunks: list[RepositoryChunk] = []
        for position, (start, level, title) in enumerate(headings):
            end = len(lines)
            for candidate_start, candidate_level, _ in headings[position + 1 :]:
                if candidate_level <= level:
                    end = candidate_start
                    break
            chunks.append(
                RepositoryChunk.create(
                    path,
                    start + 1,
                    end,
                    "".join(lines[start:end]),
                    kind="markdown-heading",
                    symbol=title,
                    file_digest=file_digest,
                )
            )
        return chunks
