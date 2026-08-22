"""Persistent, dependency-free hybrid repository index."""

from __future__ import annotations

import hashlib
import json
import math
import re
import sqlite3
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Sequence

from ..models.records import RepositoryEvidence
from ..storage.workspace import WorkspacePaths, WorkspacePolicyError
from .embeddings import DeterministicEmbeddingProvider, EmbeddingProvider
from .ingestion import IngestedFile, RepositoryIngestor
from .models import RepositoryChunk, RetrievalHit


@dataclass(slots=True, frozen=True)
class RefreshStats:
    scanned_files: int
    indexed_files: int
    skipped_files: int
    removed_files: int
    indexed_chunks: int


@dataclass(slots=True, frozen=True)
class RetrievalMetrics:
    query: str
    requested_top_k: int
    returned_hits: int
    grounded_hits: int
    refresh_attempts: int
    latency_ms: int
    retrieval_methods: tuple[str, ...]


@dataclass(slots=True, frozen=True)
class GroundedRetrieval:
    hits: tuple[RetrievalHit, ...]
    metrics: RetrievalMetrics


class StaleEvidenceError(ValueError):
    """Raised when an evidence citation no longer matches its source file."""


class RepositoryIndex:
    def __init__(
        self,
        paths: WorkspacePaths,
        *,
        ingestor: RepositoryIngestor | None = None,
        embedding_provider: EmbeddingProvider | None = None,
    ) -> None:
        self.paths = paths.ensure()
        self.ingestor = ingestor or RepositoryIngestor(self.paths)
        self.embedding_provider = embedding_provider or DeterministicEmbeddingProvider()
        self.database_path = self.paths.resolve_runtime_path("index/rag_index.db")
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def refresh(self) -> RefreshStats:
        candidates = self.ingestor.iter_files()
        indexed_files = 0
        skipped_files = 0
        indexed_chunks = 0
        seen: set[str] = set()
        with self._connection() as connection:
            for candidate in candidates:
                try:
                    ingested = self.ingestor.ingest(candidate)
                except ValueError:
                    continue
                seen.add(ingested.path)
                row = connection.execute(
                    "SELECT digest, modified_ns, size FROM files WHERE path = ?", (ingested.path,)
                ).fetchone()
                if row and row[0] == ingested.digest and row[1] == ingested.modified_ns and row[2] == ingested.size:
                    skipped_files += 1
                    continue
                connection.execute("DELETE FROM chunks WHERE path = ?", (ingested.path,))
                connection.execute(
                    "INSERT OR REPLACE INTO files(path, digest, modified_ns, size, indexed_at) VALUES (?, ?, ?, ?, ?)",
                    (ingested.path, ingested.digest, ingested.modified_ns, ingested.size, _now()),
                )
                vectors = _embed_batch(
                    self.embedding_provider,
                    [chunk.content for chunk in ingested.chunks],
                )
                if len(vectors) != len(ingested.chunks):
                    raise ValueError("embedding provider returned an unexpected vector count")
                for chunk, vector in zip(ingested.chunks, vectors, strict=True):
                    connection.execute(
                        "INSERT INTO chunks(chunk_id, path, start_line, end_line, content, kind, symbol, digest, vector) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            chunk.chunk_id,
                            chunk.path,
                            chunk.start_line,
                            chunk.end_line,
                            chunk.content,
                            chunk.kind,
                            chunk.symbol,
                            chunk.file_digest,
                            json.dumps(vector),
                        ),
                    )
                    indexed_chunks += 1
                indexed_files += 1
            existing = {row[0] for row in connection.execute("SELECT path FROM files")}
            removed = existing - seen
            for path in removed:
                connection.execute("DELETE FROM chunks WHERE path = ?", (path,))
                connection.execute("DELETE FROM files WHERE path = ?", (path,))
        return RefreshStats(len(candidates), indexed_files, skipped_files, len(removed), indexed_chunks)

    def search(self, query: str, *, top_k: int = 8) -> list[RetrievalHit]:
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query must not be empty")
        if top_k < 1 or top_k > 100:
            raise ValueError("top_k must be between 1 and 100")
        query_vector = self.embedding_provider.embed(query)
        query_tokens = set(_tokens(query))
        candidates: list[RetrievalHit] = []
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT chunk_id, path, start_line, end_line, content, kind, symbol, digest, vector FROM chunks"
            ).fetchall()
        for row in rows:
            content = row[4]
            lexical = _lexical_score(query, query_tokens, content)
            symbol = _symbol_score(query, row[6])
            vector = _cosine(query_vector, tuple(json.loads(row[8])))
            score = (0.55 * lexical) + (0.25 * vector) + (0.20 * symbol)
            if score <= 0:
                continue
            method_parts = []
            if lexical > 0:
                method_parts.append("lexical")
            if symbol > 0:
                method_parts.append("symbol")
            if vector > 0:
                method_parts.append("vector")
            evidence = RepositoryEvidence(
                chunk_id=row[0],
                path=row[1],
                start_line=row[2],
                end_line=row[3],
                content=content,
                score=round(score, 6),
                retrieval_method="+".join(method_parts) or "vector",
                file_digest=row[7],
            )
            candidates.append(RetrievalHit(evidence, score, lexical, vector, symbol))
        return sorted(candidates, key=lambda item: (-item.score, item.evidence.path, item.evidence.start_line))[:top_k]

    def retrieve_grounded(
        self,
        query: str,
        *,
        top_k: int = 8,
        maximum_retries: int = 2,
    ) -> list[RetrievalHit]:
        return list(
            self.retrieve_grounded_with_metrics(
                query,
                top_k=top_k,
                maximum_retries=maximum_retries,
            ).hits
        )

    def retrieve_grounded_with_metrics(
        self,
        query: str,
        *,
        top_k: int = 8,
        maximum_retries: int = 2,
    ) -> GroundedRetrieval:
        if maximum_retries < 0:
            raise ValueError("maximum_retries must not be negative")
        started = time.perf_counter()
        refresh_attempts = 1
        self.refresh()
        for attempt in range(maximum_retries + 1):
            hits = self.search(query, top_k=top_k)
            grounded = [hit for hit in hits if self.verify_evidence(hit.evidence)]
            if len(grounded) == len(hits):
                metrics = RetrievalMetrics(
                    query=query,
                    requested_top_k=top_k,
                    returned_hits=len(grounded),
                    grounded_hits=len(grounded),
                    refresh_attempts=refresh_attempts,
                    latency_ms=int((time.perf_counter() - started) * 1000),
                    retrieval_methods=tuple(sorted({hit.evidence.retrieval_method for hit in grounded})),
                )
                return GroundedRetrieval(tuple(grounded), metrics)
            if attempt < maximum_retries:
                refresh_attempts += 1
                self.refresh()
        raise StaleEvidenceError("retrieval evidence remained stale after bounded refresh retries")

    def verify_evidence(self, evidence: RepositoryEvidence) -> bool:
        try:
            source_path = self.paths.resolve_workspace_path(evidence.path, must_exist=True)
            raw = source_path.read_bytes()
        except (OSError, WorkspacePolicyError):
            return False
        digest = hashlib.sha256(raw).hexdigest()
        if evidence.file_digest and digest.lower() != evidence.file_digest.lower():
            return False
        try:
            lines = raw.decode("utf-8").splitlines(keepends=True)
        except UnicodeDecodeError:
            return False
        if evidence.start_line < 1 or evidence.end_line > len(lines) or evidence.end_line < evidence.start_line:
            return False
        return "".join(lines[evidence.start_line - 1 : evidence.end_line]) == evidence.content

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=5.0)
        connection.execute("PRAGMA busy_timeout = 5000")
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    @contextmanager
    def _connection(self):
        connection = self._connect()
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._connection() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS files (
                    path TEXT PRIMARY KEY,
                    digest TEXT NOT NULL,
                    modified_ns INTEGER NOT NULL,
                    size INTEGER NOT NULL,
                    indexed_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS chunks (
                    chunk_id TEXT PRIMARY KEY,
                    path TEXT NOT NULL REFERENCES files(path) ON DELETE CASCADE,
                    start_line INTEGER NOT NULL,
                    end_line INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    symbol TEXT,
                    digest TEXT NOT NULL,
                    vector TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS chunks_path_index ON chunks(path);
                CREATE INDEX IF NOT EXISTS chunks_symbol_index ON chunks(symbol);
                CREATE TABLE IF NOT EXISTS metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                """
            )
            row = connection.execute(
                "SELECT value FROM metadata WHERE key = 'embedding_signature'"
            ).fetchone()
            signature = _embedding_signature(self.embedding_provider)
            if row is None or row[0] != signature:
                connection.execute("DELETE FROM chunks")
                connection.execute("DELETE FROM files")
                connection.execute(
                    "INSERT OR REPLACE INTO metadata(key, value) VALUES ('embedding_signature', ?)",
                    (signature,),
                )


def _tokens(value: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9_]+", value.lower())


def _embed_batch(
    provider: EmbeddingProvider,
    texts: Sequence[str],
) -> tuple[tuple[float, ...], ...]:
    batch_method = getattr(provider, "embed_batch", None)
    if callable(batch_method):
        return tuple(batch_method(texts))
    return tuple(provider.embed(text) for text in texts)


def _embedding_signature(provider: EmbeddingProvider) -> str:
    explicit = getattr(provider, "signature", None)
    if isinstance(explicit, str) and explicit:
        return explicit
    provider_name = getattr(provider, "provider_name", type(provider).__qualname__)
    model = getattr(provider, "model", "legacy")
    return f"{provider_name}:{model}:{provider.dimension}"


def _lexical_score(query: str, query_tokens: set[str], content: str) -> float:
    tokens = _tokens(content)
    if not tokens or not query_tokens:
        return 0.0
    counts = {token: tokens.count(token) for token in query_tokens}
    matched = sum(count for count in counts.values())
    if matched == 0:
        return 0.0
    score = matched / math.sqrt(len(tokens))
    if query.lower().strip() in content.lower():
        score += 1.0
    return min(score, 1.0)


def _symbol_score(query: str, symbol: str | None) -> float:
    if not symbol:
        return 0.0
    normalized_query = query.strip().lower()
    normalized_symbol = symbol.lower()
    if normalized_query == normalized_symbol or normalized_query == normalized_symbol.rsplit(".", 1)[-1]:
        return 1.0
    return 0.5 if normalized_query in normalized_symbol else 0.0


def _cosine(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right):
        return 0.0
    score = sum(a * b for a, b in zip(left, right))
    return max(0.0, min(1.0, score))


def _now() -> str:
    return datetime.now(UTC).isoformat()
