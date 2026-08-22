---
title: "Phase 1 Baseline and Retrieval Report"
date: 2026-08-22
status: completed
---

# Phase 1 Baseline and Retrieval Report

## Summary

Removed obsolete workspace coupling from Git-service tests and excluded duplicated
agent/client mirrors from repository RAG. The full suite passes and the checked-in
retrieval benchmark is reproducible within the phase latency target.

## Changes

- Git tests now create isolated repositories under `CODING_AGENT_TEST_TMP`.
- Windows cleanup handles read-only loose Git objects.
- RAG ignores `.agent`, `.agents`, `.claude`, `.codex`, `.cursor`, `.gemini`,
  `.opencode`, and other generated/dependency directories.
- Skill discovery remains independent through `SkillCatalog`.

## Verification

- Focused tests: 9 passed, 0 failed.
- Full tests: 110 passed, 0 failed, 0 skipped.
- Combined line/branch coverage: 82%.
- Retrieval wall time: 2,154 ms; mean query latency 593 ms; max 735 ms.
- Retrieval: Recall@5 1.0; MRR 0.833333; citation correctness 1.0.
- Index size: 4,268,032 bytes, down from 252,977,152 bytes at the timed-out baseline.
- `git diff --check`: passed.

## Review

- Spec compliance: PASS.
- Quality review: PASS; public contracts unchanged.
- Adversarial review: no accepted findings. Client mirrors are intentionally excluded;
  source, tests, docs, root configuration, and the separate skill catalog remain available.

## Commit and Push

- Implementation commit: `a996a2e4591700ceacd4e572b87354553f642f57`.
- Remote status: pushed to `origin/main`; remote SHA verified equal.

## Known Limitations

- Recall@1 and Recall@3 are not emitted by the current evaluation schema; Phase 4 will add
  final acceptance metrics if required.

## Unresolved Questions

- None.
