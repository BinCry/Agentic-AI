from __future__ import annotations

import unittest

from coding_agent.llm.openai_client import OpenAIHttpClient, OpenAIResponseError
from coding_agent.rag.embeddings import DeterministicEmbeddingProvider, OpenAIEmbeddingProvider
from coding_agent.rag.index import RepositoryIndex
from coding_agent.storage.workspace import WorkspacePaths

from tests.openai_provider_test_support import QueueTransport, response
from tests.support import WorkspaceTestCase


class LegacyEmbeddingProvider:
    dimension = 8

    def embed(self, text: str) -> tuple[float, ...]:
        return (float(len(text)), 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)


class OpenAIEmbeddingTests(WorkspaceTestCase):
    def test_embedding_batches_preserve_input_order(self) -> None:
        first = [float(index) for index in range(8)]
        second = [float(index + 10) for index in range(8)]
        third = [float(index + 20) for index in range(8)]
        transport = QueueTransport(
            [
                response(
                    200,
                    {
                        "data": [
                            {"index": 1, "embedding": second},
                            {"index": 0, "embedding": first},
                        ]
                    },
                ),
                response(200, {"data": [{"index": 0, "embedding": third}]}),
            ]
        )
        provider = OpenAIEmbeddingProvider(
            OpenAIHttpClient("test-key", transport=transport),
            dimension=8,
            batch_size=2,
        )
        vectors = provider.embed_batch(["first", "second", "third"])
        self.assertEqual(vectors, (tuple(first), tuple(second), tuple(third)))
        self.assertEqual(len(transport.calls), 2)

    def test_embedding_rejects_dimension_mismatch(self) -> None:
        transport = QueueTransport(
            [response(200, {"data": [{"index": 0, "embedding": [0.0, 1.0]}]})]
        )
        provider = OpenAIEmbeddingProvider(
            OpenAIHttpClient("test-key", transport=transport),
            dimension=8,
        )
        with self.assertRaisesRegex(OpenAIResponseError, "dimension"):
            provider.embed("value")

    def test_embedding_rejects_non_finite_values(self) -> None:
        provider = OpenAIEmbeddingProvider(
            OpenAIHttpClient("test-key", transport=QueueTransport([])),
            dimension=8,
        )
        payload = {"data": [{"index": 0, "embedding": [float("nan")] * 8}]}
        with self.assertRaisesRegex(OpenAIResponseError, "dimension"):
            provider._ordered_vectors(payload, 1)

    def test_index_rebuilds_when_embedding_signature_changes(self) -> None:
        (self.test_root / "module.py").write_text("value = 'needle'\n", encoding="utf-8")
        paths = WorkspacePaths.create(self.test_root).ensure()
        first = RepositoryIndex(
            paths,
            embedding_provider=DeterministicEmbeddingProvider(dimension=8),
        ).refresh()
        second = RepositoryIndex(
            paths,
            embedding_provider=DeterministicEmbeddingProvider(dimension=16),
        ).refresh()
        self.assertEqual(first.indexed_files, 1)
        self.assertEqual(second.indexed_files, 1)
        self.assertEqual(second.skipped_files, 0)

    def test_index_accepts_legacy_single_text_embedding_provider(self) -> None:
        (self.test_root / "module.py").write_text("legacy needle\n", encoding="utf-8")
        index = RepositoryIndex(
            WorkspacePaths.create(self.test_root).ensure(),
            embedding_provider=LegacyEmbeddingProvider(),
        )
        self.assertEqual(index.refresh().indexed_files, 1)
        self.assertTrue(index.search("legacy"))


if __name__ == "__main__":
    unittest.main()
