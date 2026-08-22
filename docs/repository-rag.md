# Repository RAG

The repository retrieval layer is read-only and does not modify source files
or introduce an external vector database. Deterministic embeddings remain the
offline default; a configured production embedding adapter can call OpenAI.

## Pipeline

```text
WorkspacePaths
    -> RepositoryIngestor (filters, UTF-8, size limit, SHA-256)
    -> PythonAstChunker / MarkdownHeadingChunker / LineChunker
    -> SQLite persistent index (.coding-agent/index/rag_index.db)
    -> lexical + symbol + configured vector scoring
    -> grounded RepositoryEvidence with exact line citations
```

## Ingestion and chunking

The ingestor indexes supported text extensions only and skips `.git`, agent
client mirrors, `.coding-agent`, `.tmp`, virtual environments, build output,
coverage and `node_modules`. Skills remain available through the separate
`SkillCatalog`. Files larger than 1 MB or invalid UTF-8 are excluded.
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

`DeterministicEmbeddingProvider` keeps tests and CI offline and reproducible.
`OpenAIEmbeddingProvider` supports bounded ordered batches through the same
interface. The index persists a provider/model/dimension signature and safely
rebuilds vectors when that signature changes. Legacy providers implementing
only `dimension` and `embed()` remain compatible.

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
`CodingWorkflowOrchestrator` evaluates at most four unique analysis queries
during `RETRIEVING`, retaining grounded hits from later queries when an earlier
query is empty. It then enters `VERIFYING_EVIDENCE`; evidence is sorted by
score before it is projected into prompts, and planning cannot start without
current evidence.

## Verification

Fixtures cover AST symbols and syntax fallback, Markdown fenced code, ingestion
filters, incremental refresh, persistent reopen, stale evidence detection,
grounded retrieval, metrics and controller state updates. Run the full suite
using the command in [Testing and Safety](testing-and-safety.md).
