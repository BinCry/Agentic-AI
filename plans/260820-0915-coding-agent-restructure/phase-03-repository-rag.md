# Phase 03: Repository RAG

## Context Links

- Plan: [plan.md](./plan.md)

## Overview

- **Priority:** high
- **Status:** completed
- **Description:** Implement ingestion, semantic chunking, indexing, hybrid retrieval, grounding, and citation.

## Requirements

- Code-aware Python AST chunking and extensible parser adapters.
- Heading-aware documentation chunking.
- Lexical, vector, and symbol retrieval with scores and metadata.
- Exact current-file grounding before edits and explicit retrieval recovery.

## Todo

- [x] Implement ingestion filters and metadata.
- [x] Implement chunkers and embedding interface.
- [x] Implement persistent hybrid index.
- [x] Implement grounding, citations, and recovery.
- [x] Add retrieval fixtures and metrics.

## Success Criteria

- Retrieval returns scored evidence with exact path and line citations.
- Current-file grounding is verified before a patch can execute.
- Index refresh is incremental and stale evidence recovery is bounded.

## Risk Assessment

| Risk | Impact | Mitigation |
|---|---|---|
| Stale index | high | Store file digest and verify source before use |

## Next Steps

- Connect retrieval and tools to the workflow controller in Phase 3 implementation; Phase 4 will add autonomous orchestration.

## Delivered Modules

- `src/coding_agent/rag/ingestion.py`: workspace-bounded file discovery, filtering, digest and metadata.
- `src/coding_agent/rag/chunkers.py`: Python AST, Markdown heading and bounded text chunking.
- `src/coding_agent/rag/index.py`: persistent SQLite hybrid index, deterministic embedding interface, grounding and metrics.
- `src/coding_agent/rag/models.py`: typed chunks and scored retrieval hits.
- `repo.retrieve`: read-only MCP/controller tool that persists evidence and queries into task state.
- Patch execution now requires current grounded evidence for the target file.

## Verification

- Full regression and Phase 3 fixtures: 70 tests passed; 2 Windows symlink tests skipped because the current account lacks symlink privilege.
- No external vector database, embedding service or autonomous LLM loop was added.
