# Phase 03: Repository RAG

## Context Links

- Plan: [plan.md](./plan.md)

## Overview

- **Priority:** high
- **Status:** pending
- **Description:** Implement ingestion, semantic chunking, indexing, hybrid retrieval, grounding, and citation.

## Requirements

- Code-aware Python AST chunking and extensible parser adapters.
- Heading-aware documentation chunking.
- Lexical, vector, and symbol retrieval with scores and metadata.
- Exact current-file grounding before edits and explicit retrieval recovery.

## Todo

- [ ] Implement ingestion filters and metadata.
- [ ] Implement chunkers and embedding interface.
- [ ] Implement persistent hybrid index.
- [ ] Implement grounding, citations, and recovery.
- [ ] Add retrieval fixtures and metrics.

## Success Criteria

- Retrieval returns scored evidence with exact path and line citations.

## Risk Assessment

| Risk | Impact | Mitigation |
|---|---|---|
| Stale index | high | Store file digest and verify source before use |

## Next Steps

- Connect retrieval and tools to the workflow controller.
