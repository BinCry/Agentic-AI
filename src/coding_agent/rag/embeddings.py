"""Offline and production embedding providers for repository retrieval."""

from __future__ import annotations

import hashlib
import math
import os
import re
from typing import Any, Mapping, Protocol, Sequence

from ..llm.openai_client import OpenAIConfigurationError, OpenAIHttpClient, OpenAIResponseError


class EmbeddingProvider(Protocol):
    dimension: int

    def embed(self, text: str) -> tuple[float, ...]: ...


class DeterministicEmbeddingProvider:
    """Stable offline vectorizer for tests and small local repositories."""

    provider_name = "deterministic"
    model = "sha256-token-v1"

    def __init__(self, dimension: int = 128) -> None:
        if dimension < 8:
            raise ValueError("embedding dimension must be at least 8")
        self.dimension = dimension

    @property
    def signature(self) -> str:
        return f"{self.provider_name}:{self.model}:{self.dimension}"

    def embed(self, text: str) -> tuple[float, ...]:
        vector = [0.0] * self.dimension
        for token in re.findall(r"[A-Za-z0-9_]+", text.lower()):
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimension
            vector[index] += 1.0 if digest[4] % 2 else -1.0
        norm = math.sqrt(sum(value * value for value in vector))
        return tuple(value / norm for value in vector) if norm else tuple(vector)

    def embed_batch(self, texts: Sequence[str]) -> tuple[tuple[float, ...], ...]:
        return tuple(self.embed(text) for text in texts)


class OpenAIEmbeddingProvider:
    """Ordered, batched adapter for the OpenAI embeddings endpoint."""

    provider_name = "openai"

    def __init__(
        self,
        client: OpenAIHttpClient,
        *,
        model: str = "text-embedding-3-small",
        dimension: int = 1_536,
        batch_size: int = 32,
    ) -> None:
        if not model.strip() or dimension < 8:
            raise OpenAIConfigurationError("embedding model and dimension are invalid")
        if batch_size < 1 or batch_size > 128:
            raise OpenAIConfigurationError("embedding batch size must be between 1 and 128")
        self.client = client
        self.model = model.strip()
        self.dimension = dimension
        self.batch_size = batch_size

    @classmethod
    def from_env(
        cls,
        environment: Mapping[str, str] | None = None,
        *,
        client: OpenAIHttpClient | None = None,
    ) -> "OpenAIEmbeddingProvider":
        values = os.environ if environment is None else environment
        try:
            dimension = int(values.get("OPENAI_EMBEDDING_DIMENSION", "1536"))
            batch_size = int(values.get("OPENAI_EMBEDDING_BATCH_SIZE", "32"))
        except ValueError as exc:
            raise OpenAIConfigurationError(
                "embedding dimension and batch size must be integers"
            ) from exc
        return cls(
            client or OpenAIHttpClient.from_env(values),
            model=values.get("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"),
            dimension=dimension,
            batch_size=batch_size,
        )

    @property
    def signature(self) -> str:
        return f"{self.provider_name}:{self.model}:{self.dimension}"

    def embed(self, text: str) -> tuple[float, ...]:
        vectors = self.embed_batch([text])
        return vectors[0]

    def embed_batch(self, texts: Sequence[str]) -> tuple[tuple[float, ...], ...]:
        normalized = list(texts)
        if any(not isinstance(text, str) or not text.strip() for text in normalized):
            raise ValueError("embedding inputs must be non-empty strings")
        vectors: list[tuple[float, ...]] = []
        for offset in range(0, len(normalized), self.batch_size):
            batch = normalized[offset : offset + self.batch_size]
            payload = self.client.post_json(
                "/embeddings",
                {"model": self.model, "input": batch},
            )
            vectors.extend(self._ordered_vectors(payload, len(batch)))
        return tuple(vectors)

    def _ordered_vectors(
        self,
        payload: dict[str, Any],
        expected_count: int,
    ) -> tuple[tuple[float, ...], ...]:
        data = payload.get("data")
        if not isinstance(data, list) or len(data) != expected_count:
            raise OpenAIResponseError("embeddings response count did not match the request")
        ordered: list[tuple[float, ...] | None] = [None] * expected_count
        for item in data:
            if not isinstance(item, dict):
                raise OpenAIResponseError("embedding item must be an object")
            index = item.get("index")
            values = item.get("embedding")
            if not isinstance(index, int) or isinstance(index, bool) or not 0 <= index < expected_count:
                raise OpenAIResponseError("embedding item index is invalid")
            if ordered[index] is not None or not isinstance(values, list):
                raise OpenAIResponseError("embedding response contains duplicate or invalid items")
            vector = tuple(
                float(value)
                for value in values
                if isinstance(value, (int, float)) and not isinstance(value, bool)
            )
            if (
                len(vector) != self.dimension
                or len(vector) != len(values)
                or any(not math.isfinite(value) for value in vector)
            ):
                raise OpenAIResponseError("embedding vector dimension is invalid")
            ordered[index] = vector
        if any(vector is None for vector in ordered):
            raise OpenAIResponseError("embedding response omitted an input index")
        return tuple(vector for vector in ordered if vector is not None)
