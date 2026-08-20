# Phase 06: Evaluation and Documentation

## Context Links

- Plan: [plan.md](./plan.md)

## Overview

- **Priority:** medium
- **Status:** completed
- **Description:** Add benchmark data, metrics, failure analysis, operating docs, and risk controls.

## Requirements

- Machine-readable benchmark cases and evaluation results.
- Recall@K, MRR, citation correctness, latency, completion, repair, regression, and tool-failure metrics.
- Architecture, workflow, RAG, MCP, permission, evaluation, and run guides.
- Document prompt-injection, stale-index, leakage, permission, and repair-loop risks.

## Todo

- [x] Add versioned benchmark schema and sample fixtures.
- [x] Add retrieval and coding-agent metrics.
- [x] Add machine-readable failure-analysis reports.
- [x] Complete operating, evaluation and architecture documentation.

## Success Criteria

- Evaluation commands produce honest machine-readable results without fabricated
  passes; missing task samples remain explicit as `null` metrics.

## Delivered

- `evaluation/runner.py` validates benchmark schema and computes Recall@K, MRR,
  citation correctness, latency, completion, repair, regression and tool-failure
  metrics.
- `coding-agent evaluate` emits JSON and accepts repeated `--task-id` samples.
- `tests/fixtures/benchmarks/retrieval_cases.json` provides three deterministic
  repository cases.
- Evaluation method and measured failure analysis are documented in
  `docs/evaluation.md` and this phase's report.

## Verification

- Full regression after Phase 6 implementation: 78 tests passed, 2 Windows
  symlink tests skipped because symlink privilege is unavailable.

## Risk Assessment

| Risk | Impact | Mitigation |
|---|---|---|
| Misleading benchmark | high | Separate sample fixtures from measured results |

## Next Steps

- Conduct final release readiness review.
