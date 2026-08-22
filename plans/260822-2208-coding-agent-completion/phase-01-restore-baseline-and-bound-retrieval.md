---
phase: 1
title: "Restore Baseline and Bound Retrieval"
status: completed
priority: P1
effort: "1h"
dependencies: []
---

# Phase 1: Restore Baseline and Bound Retrieval

## Context Links

- [Audit Report](./reports/audit-260822-2208-current-state.md)
- [Existing RAG](../../260820-0915-coding-agent-restructure/phase-03-repository-rag.md)

## Requirements

- Replace obsolete absolute test paths with isolated D: fixtures.
- Exclude client mirrors and agent configuration roots from repository RAG.
- Preserve the separate skill catalog as the source for skill discovery.
- Re-run tests, coverage, CLI smoke, and retrieval benchmark.

## Related Code Files

- Modify `tests/test_execution_tools.py`.
- Modify `src/coding_agent/rag/ingestion.py`.
- Modify `tests/test_rag.py`.
- Update predecessor plan status only after its delivered baseline passes.
- Create the phase report under this plan's `reports/` directory.

## Implementation Steps

1. Create a minimal Git repository inside each relevant test fixture.
2. Add hidden client/config roots to the default ingestion exclusions.
3. Test exclusion behavior and ensure normal source/docs remain ingestible.
4. Run focused tests, full regression, coverage, and benchmark.
5. Review diff, commit, push, and verify remote SHA.

## Tests

- Focus: `tests.test_execution_tools`, `tests.test_rag`.
- Regression: full `unittest` suite.
- Benchmark: checked-in retrieval cases with top-k 5.

## Success Criteria

- [x] All discovered tests pass.
- [x] Benchmark completes within 30 seconds on the current workspace.
- [x] Runtime index no longer contains duplicated client-mirror content.
- [x] No write targets use C:.

## Risk and Rollback

- Risk: excluding skill mirrors could remove useful coding evidence.
- Mitigation: runtime skill discovery remains independent; source/tests/docs stay indexed.
- Rollback: revert the exclusion set and retain the isolated test fix.
