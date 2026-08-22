---
phase: 2
title: "Add Production AI Providers"
status: in-progress
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

- [ ] Offline provider tests cover all typed failure paths.
- [ ] Existing deterministic evaluation remains reproducible.
- [ ] Optional live smoke clearly reports unavailable credentials instead of fabricating success.
- [ ] No new general provider framework or vendor fan-out is introduced.

## Risk and Rollback

- Network/API behavior can change; isolate it behind current public contracts.
- Roll back by selecting deterministic embeddings and leaving provider config unset.
