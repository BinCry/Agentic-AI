from __future__ import annotations

import unittest

from coding_agent.rag.chunkers import MarkdownHeadingChunker, PythonAstChunker
from coding_agent.rag.index import RepositoryIndex
from coding_agent.rag.ingestion import RepositoryIngestor
from coding_agent.storage.workspace import WorkspacePaths

from tests.support import WorkspaceTestCase


class RepositoryRagTests(WorkspaceTestCase):
    def make_paths(self) -> WorkspacePaths:
        return WorkspacePaths.create(self.test_root).ensure()

    def test_python_chunker_preserves_symbol_lines_and_falls_back_on_syntax_error(self) -> None:
        source = "class Example:\n    def run(self):\n        return 'needle'\n"
        chunks = PythonAstChunker().chunk("module.py", source, "a" * 64)
        self.assertEqual([chunk.symbol for chunk in chunks], ["Example", "Example.run"])
        self.assertEqual(chunks[1].start_line, 2)
        self.assertIn("return 'needle'", chunks[1].content)
        fallback = PythonAstChunker().chunk("broken.py", "def broken(:\n", "b" * 64)
        self.assertEqual(fallback[0].kind, "text")

    def test_markdown_chunker_ignores_headings_inside_fenced_code(self) -> None:
        source = "# Intro\ntext\n## Details\nmore\n```md\n# not a heading\n```\n"
        chunks = MarkdownHeadingChunker().chunk("README.md", source, "c" * 64)
        self.assertEqual([chunk.symbol for chunk in chunks], ["Intro", "Details"])
        self.assertIn("# not a heading", chunks[1].content)

    def test_ingestion_filters_directories_and_large_files(self) -> None:
        (self.test_root / "src").mkdir()
        (self.test_root / "src" / "module.py").write_text("value = 1\n", encoding="utf-8")
        ignored_roots = (
            ".agent",
            ".agents",
            ".claude",
            ".codex",
            ".cursor",
            ".gemini",
            ".git",
            ".opencode",
        )
        for ignored_root in ignored_roots:
            directory = self.test_root / ignored_root
            directory.mkdir()
            (directory / "ignored.py").write_text("ignored = True\n", encoding="utf-8")
        (self.test_root / "large.py").write_text("x" * 100, encoding="utf-8")
        ingestor = RepositoryIngestor(self.make_paths(), maximum_file_bytes=50)
        paths = {str(item.relative_to(self.test_root)) for item in ingestor.iter_files()}
        self.assertEqual(paths, {"src\\module.py"})

    def test_persistent_hybrid_index_returns_grounded_citation_and_reuses_digest(self) -> None:
        target = self.test_root / "module.py"
        target.write_text("def run():\n    return 'needle'\n", encoding="utf-8")
        index = RepositoryIndex(self.make_paths())
        first = index.refresh()
        self.assertEqual(first.indexed_files, 1)
        second = index.refresh()
        self.assertEqual(second.skipped_files, 1)
        retrieval = index.retrieve_grounded_with_metrics("needle")
        hits = list(retrieval.hits)
        self.assertTrue(hits)
        self.assertEqual(retrieval.metrics.grounded_hits, len(hits))
        self.assertGreaterEqual(retrieval.metrics.refresh_attempts, 1)
        evidence = hits[0].evidence
        self.assertEqual(evidence.path, "module.py")
        self.assertEqual(evidence.start_line, 1)
        self.assertTrue(index.verify_evidence(evidence))
        target.write_text("def run():\n    return 'changed'\n", encoding="utf-8")
        self.assertFalse(index.verify_evidence(evidence))
        refreshed = index.retrieve_grounded("changed")
        self.assertTrue(refreshed)
        reopened = RepositoryIndex(self.make_paths())
        self.assertTrue(reopened.search("changed"))


if __name__ == "__main__":
    unittest.main()
