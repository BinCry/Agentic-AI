# Repository RAG

Phase 3 adds a dependency-free repository retrieval layer on top of the Phase
2 workspace boundary. It is deterministic and read-only: it does not call an
LLM, modify source files or introduce a vector database.

## Pipeline

```text
WorkspacePaths
    -> RepositoryIngestor (filters, UTF-8, size limit, SHA-256)
    -> PythonAstChunker / MarkdownHeadingChunker / LineChunker
    -> SQLite persistent index (.coding-agent/index/rag_index.db)
    -> lexical + symbol + deterministic vector scoring
    -> grounded RepositoryEvidence with exact line citations
```

## Ingestion and chunking

The ingestor indexes supported text extensions only and skips `.git`,
`.coding-agent`, `.tmp`, virtual environments, build output, coverage and
`node_modules`. Files larger than 1 MB or that are not valid UTF-8 are excluded.
Every indexed file stores a SHA-256 digest, size and modification timestamp.

Python files are parsed with the standard-library `ast` module. Classes,
functions and nested qualified symbols become chunks using their exact
`lineno`/`end_lineno` range. Syntax-error files fall back to bounded line
chunks instead of stopping the whole ingestion pass.

Markdown headings are chunked by heading level. Fenced-code headings are not
treated as document headings. Other supported text is split into bounded line
chunks with a small overlap.

## Persistent hybrid index

The index uses SQLite from the Python standard library and lives under the
workspace runtime root. Refresh is incremental: unchanged path/digest/metadata
records are skipped; changed files replace their chunks in one transaction; and
deleted files are removed.

Retrieval combines:

- lexical token and phrase score;
- exact/partial symbol score for Python chunks;
- a stable hashed vector score through the `EmbeddingProvider` interface.

`DeterministicEmbeddingProvider` keeps tests offline and reproducible. A future
provider may implement the same interface without changing the core index.

## Grounding and recovery

`RepositoryEvidence` contains the chunk ID, relative path, start/end lines,
source content, retrieval method, score and file digest. Before a patch is
allowed, at least one retrieved evidence item for the target path must still
match the current file digest and exact line content. The patch service also
checks its expected source digest.

Grounded retrieval refreshes the index before searching and retries stale
evidence only within the configured bounded retrieval retry limit. Retrieval
metrics report requested top-k, returned/grounded hits, refresh attempts,
latency and retrieval methods.

## Controlled tool

Phase 2's read-only MCP surface now includes `repo.retrieve`:

```json
{
  "name": "repo.retrieve",
  "request_id": "retrieve-1",
  "arguments": {"query": "approval_return_status", "top_k": 5}
}
```

The controller stores returned evidence in `CodingTaskState.retrieved_evidence`
and records the query in `retrieval_queries`. Phase 4's
`CodingWorkflowOrchestrator` calls retrieval during `RETRIEVING` before it can
request a mutation, so the patch boundary can require current evidence for the
target file.

## Verification

Fixtures cover AST symbols and syntax fallback, Markdown fenced code, ingestion
filters, incremental refresh, persistent reopen, stale evidence detection,
grounded retrieval, metrics and controller state updates. Run the full suite
using the command in [Testing and Safety](testing-and-safety.md).
