"""Bounded repository reading, text search and Python symbol inspection."""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path

from ..storage.workspace import WorkspacePaths, WorkspacePolicyError


class RepositoryToolError(ValueError):
    """Raised when a repository read request cannot be fulfilled safely."""


@dataclass(slots=True, frozen=True)
class SearchMatch:
    path: str
    line: int
    text: str


@dataclass(slots=True, frozen=True)
class Symbol:
    name: str
    kind: str
    path: str
    line: int
    end_line: int | None


class RepositoryReadService:
    def __init__(
        self,
        paths: WorkspacePaths,
        *,
        maximum_file_bytes: int = 1_000_000,
        maximum_matches: int = 200,
    ) -> None:
        self.paths = paths
        self.maximum_file_bytes = maximum_file_bytes
        self.maximum_matches = maximum_matches

    def read_file(self, path: str) -> str:
        target = self._file_path(path)
        self._check_size(target)
        try:
            return target.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise RepositoryToolError(f"file is not valid UTF-8: {path}") from exc
        except OSError as exc:
            raise RepositoryToolError(f"cannot read file {path}: {exc}") from exc

    def list_files(self, path: str = ".", *, maximum_files: int = 500) -> list[str]:
        if maximum_files < 1 or maximum_files > 2_000:
            raise RepositoryToolError("maximum_files must be between 1 and 2000")
        root = self.paths.resolve_workspace_path(path, must_exist=True)
        files = [root] if root.is_file() else self._iter_files(root)
        return [
            str(item.relative_to(self.paths.workspace_root)).replace("\\", "/")
            for item in files[:maximum_files]
        ]

    def search_text(
        self,
        query: str,
        *,
        path: str = ".",
        regular_expression: bool = False,
        maximum_matches: int | None = None,
    ) -> list[SearchMatch]:
        if not query or len(query) > 4_000:
            raise RepositoryToolError("query must contain 1-4000 characters")
        if regular_expression:
            try:
                matcher = re.compile(query)
            except re.error as exc:
                raise RepositoryToolError(f"invalid regular expression: {exc}") from exc
        else:
            matcher = None
        root = self.paths.resolve_workspace_path(path, must_exist=True)
        files = [root] if root.is_file() else self._iter_files(root)
        limit = maximum_matches or self.maximum_matches
        if limit < 1 or limit > self.maximum_matches:
            raise RepositoryToolError(f"maximum_matches must be between 1 and {self.maximum_matches}")
        matches: list[SearchMatch] = []
        for file_path in files:
            if len(matches) >= limit:
                break
            try:
                self._check_size(file_path)
                lines = file_path.read_text(encoding="utf-8").splitlines()
            except (OSError, UnicodeDecodeError):
                continue
            for line_number, line in enumerate(lines, start=1):
                found = bool(matcher.search(line)) if matcher else query in line
                if found:
                    matches.append(
                        SearchMatch(
                            str(file_path.relative_to(self.paths.workspace_root)),
                            line_number,
                            line[:4_000],
                        )
                    )
                    if len(matches) >= limit:
                        break
        return matches

    def find_symbols(self, path: str) -> list[Symbol]:
        target = self._file_path(path)
        if target.suffix.lower() != ".py":
            raise RepositoryToolError("find_symbols currently supports Python files only")
        source = self.read_file(path)
        try:
            tree = ast.parse(source, filename=str(target))
        except SyntaxError as exc:
            raise RepositoryToolError(f"cannot parse Python file {path}: {exc}") from exc
        relative = str(target.relative_to(self.paths.workspace_root))
        symbols: list[Symbol] = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                symbols.append(
                    Symbol(
                        name=node.name,
                        kind=("class" if isinstance(node, ast.ClassDef) else "function"),
                        path=relative,
                        line=node.lineno,
                        end_line=getattr(node, "end_lineno", None),
                    )
                )
        return sorted(symbols, key=lambda item: (item.line, item.name))

    def _file_path(self, path: str) -> Path:
        try:
            target = self.paths.resolve_workspace_path(path, must_exist=True)
        except WorkspacePolicyError as exc:
            raise RepositoryToolError(str(exc)) from exc
        if not target.is_file():
            raise RepositoryToolError(f"path is not a file: {path}")
        return target

    def _check_size(self, path: Path) -> None:
        try:
            size = path.stat().st_size
        except OSError as exc:
            raise RepositoryToolError(f"cannot stat file {path}: {exc}") from exc
        if size > self.maximum_file_bytes:
            raise RepositoryToolError(
                f"file exceeds maximum size of {self.maximum_file_bytes} bytes: {path}"
            )

    def _iter_files(self, root: Path) -> list[Path]:
        ignored = {".git", ".coding-agent", "node_modules", "__pycache__"}
        files: list[Path] = []
        for candidate in root.rglob("*"):
            if any(part in ignored for part in candidate.parts):
                continue
            if not candidate.is_file():
                continue
            try:
                resolved = self.paths.resolve_workspace_path(candidate, must_exist=True)
            except WorkspacePolicyError:
                continue
            if resolved.is_file():
                files.append(resolved)
        return sorted(files)
