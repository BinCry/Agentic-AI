---
title: "Coding Agent Current-State Audit"
date: 2026-08-22
status: verified
---

# Coding Agent Current-State Audit

## Summary

The repository is a substantial Coding Agent core, not a disconnected scaffold.
Completion gaps are concentrated at production provider wiring, executable CLI
integration, retrieval scope/performance, and enforced release gates.

## Capability Matrix

| Capability | Evidence | Status | Gap / Action |
|---|---|---|---|
| Persistent task state and bounded workflow | `models/task_state.py`, `workflow/engine.py`, workflow tests | VERIFIED_COMPLETE | None |
| Structured decisions and validation | `models/decisions.py`, `llm/structured_output.py` | VERIFIED_COMPLETE | None |
| Skill discovery/routing | `skills/catalog.py`, `skills/router.py`, CLI skills smoke | VERIFIED_COMPLETE | None |
| Repository ingestion/chunking/index/citation | `rag/*`, RAG tests | PARTIAL | Client mirrors make full benchmark exceed 120s |
| Semantic production embedding | Only `DeterministicEmbeddingProvider` exists | MISSING | Add one batched provider and metadata invalidation |
| Controlled MCP/tools/approval/path guards | `tools/*`, `mcp/server.py`, security tests | VERIFIED_COMPLETE | Preserve contracts |
| End-to-end orchestrator/repair/review/final report | `workflow/orchestrator.py`, fixture tests | VERIFIED_COMPLETE | Not exposed through operational CLI |
| Crash recovery/context/error taxonomy | checkpoint, approval ledger, context, typed errors | VERIFIED_COMPLETE | Expand acceptance coverage only |
| Evaluation schema and metrics | `evaluation/runner.py`, evaluation tests | PARTIAL | Current full-repo benchmark not reproducible in 120s |
| Production LLM provider | Protocol and fake test providers only | MISSING | Add one Responses API adapter |
| Packaging/CLI | `pyproject.toml`, import/help/skills smoke pass | PARTIAL | No workflow run command; clean-install gate unverified |
| CI/coverage enforcement | branch coverage enabled, `fail_under = 0` | MISSING | Add measured gate and CI |

## Measured Baseline

- Syntax compilation passed.
- Tests: 110 run, 108 pass, 2 error.
- Errors: obsolete `D:/HK5/AGENTIC` in two execution-tool tests.
- Combined coverage: 82% with branch coverage enabled.
- Retrieval evaluation: timed out after 120 seconds.
- Partial index size at timeout: 252,977,152 bytes.
- Tracked files: 6,700; 6,339 are duplicated client/agent roots.
- CLI import, help, and skill discovery passed; 83 skills loaded.
- GitHub authentication verified; branch is `main`; remote is `origin`.
- Active grading-label search returned no matches.

## Decisions

- Reuse current architecture and public contracts.
- Exclude client mirrors from repository RAG; keep skill catalog separate.
- Add one OpenAI production path, not a provider registry.
- Keep deterministic/offline behavior for tests and CI.
- Default CLI behavior pauses for approval; automation requires explicit opt-in.

## Unresolved Questions

- Live provider smoke depends on whether `OPENAI_API_KEY` is available at validation time.
