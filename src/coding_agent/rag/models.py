"""Typed records produced by the Phase 3 repository index."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from ..models.records import RepositoryEvidence


@dataclass(slots=True, frozen=True)
class RepositoryChunk:
    chunk_id: str
    path: str
    start_line: int
    end_line: int
    content: str
    kind: str
    symbol: str | None
    file_digest: str

    @classmethod
    def create(
        cls,
        path: str,
        start_line: int,
        end_line: int,
        content: str,
        *,
        kind: str,
        symbol: str | None,
        file_digest: str,
    ) -> "RepositoryChunk":
        identity = f"{path}:{start_line}:{end_line}:{kind}:{symbol or ''}:{file_digest}"
        chunk_id = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:32]
        return cls(chunk_id, path, start_line, end_line, content, kind, symbol, file_digest)


@dataclass(slots=True, frozen=True)
class RetrievalHit:
    evidence: RepositoryEvidence
    score: float
    lexical_score: float
    vector_score: float
    symbol_score: float
