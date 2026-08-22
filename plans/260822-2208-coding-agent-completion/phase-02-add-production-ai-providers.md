---
phase: 2
title: "Add Production AI Providers"
status: completed
priority: P1
effort: "3h"
dependencies: [1]
---

# Phase 2: Add Production AI Providers

## Requirements

- Add one OpenAI Responses API LLM provider behind `LLMProvider`.
- Add one batched OpenAI embeddings provider behind the RAG interface.
- Keep deterministic embeddings as the offline/test default.
- Use environment configuration, bounded timeout/retry, typed errors, stable ordering,
  dimension validation, and no secret logging.
- Rebuild stale vectors when provider/model/dimension metadata changes.

## Related Code Files

- Create `src/coding_agent/llm/openai_client.py` and `openai_provider.py`.
- Create `src/coding_agent/rag/embeddings.py`.
- Modify `src/coding_agent/rag/index.py` and package exports.
- Create provider tests; extend RAG tests for batching and index invalidation.

## Implementation Steps

1. Implement a small injectable HTTPS JSON transport for official API endpoints.
2. Map Responses API output into the existing `LLMResponse` contract.
3. Implement ordered embedding batches using `text-embedding-3-small` by default.
4. Persist embedding metadata and force safe reindex on configuration drift.
5. Test success, retry, timeout, malformed response, ordering, dimension mismatch,
   and secret-safe errors without network calls.

## Tests and Acceptance

- [x] Offline provider tests cover configuration, retry, response, ordering,
  dimension, finite-value, and compatibility failure paths.
- [x] Existing deterministic evaluation remains reproducible; full suite passes.
- [x] Live smoke reports unavailable because no credential is present.
- [x] No general provider framework or vendor fan-out introduced.

## Completion Evidence

- Implementation commit: `72bca15e79731a3cdf52b71d903e0559f8909121`.
- Focused provider/RAG tests: 17 passed.
- Full suite: 122 passed; combined branch coverage 81%.
- Local and `origin/main` SHA matched after push.
- Report: [Phase 2 Production AI Providers](./reports/phase-02-production-ai-providers-report.md).

## Risk and Rollback

- Network/API behavior can change; isolate it behind current public contracts.
- Roll back by selecting deterministic embeddings and leaving provider config unset.
