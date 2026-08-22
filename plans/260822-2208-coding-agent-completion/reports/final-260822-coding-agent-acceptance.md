# Coding Agent Production Acceptance

Date: 2026-08-22

## Outcome

Production completion accepted. The existing architecture now has bounded
repository retrieval, production OpenAI Responses and embedding adapters, a
persisted executable CLI workflow, enforced coverage, reproducible packaging,
and remote CI verification.

## Delivery Evidence

- Phase 1 baseline and bounded retrieval: `a996a2e4591700ceacd4e572b87354553f642f57`.
- Phase 2 production providers: `72bca15e79731a3cdf52b71d903e0559f8909121`.
- Phase 3 executable workflow: `5640007035ed02760ab5591b0741d4791ab8d2dc`.
- Phase 4 quality gates: `c7ec9cb7a173b11a9edcbc9352522e0adf6e48ad`.
- Cross-platform CI correction: `0396b12d773225904a4b3666743881ba54c1b950`.

## Acceptance Results

- Full local suite: 131 passed.
- Combined branch coverage: 82%; enforced minimum: 80%.
- Focused MCP, security, approval, recovery, and end-to-end gate: 47 passed.
- Compile, diff formatting, secret-pattern, and grading-label scans: passed.
- Wheel: 83,243 bytes; SHA-256
  `f53680d51cf4a481dce2cc07d2f3a86691d337131e3fbbd43e90785407bc0018`.
- Installed-wheel import, CLI help, and 83-skill discovery smoke: passed.
- GitHub Actions run [32583019842](https://github.com/BinCry/Agentic-AI/actions/runs/32583019842):
  Python 3.11 and 3.12 jobs passed coverage, wheel build, and installed CLI smoke.

## Retrieval Results

| Top-k | Recall | MRR | Citation correctness | Mean / p95 / max latency | Failures |
|---:|---:|---:|---:|---:|---:|
| 1 | 0.6667 | 0.6667 | 1.0 | 718 / 647 / 868 ms | 1 |
| 3 | 1.0 | 0.8333 | 1.0 | 636 / 638 / 643 ms | 0 |
| 5 | 1.0 | 0.8333 | 1.0 | 635 / 634 / 642 ms | 0 |

## Residual Limits

- Live OpenAI smoke was unavailable because `OPENAI_API_KEY` was absent; it was
  not counted as a pass.
- Offline deterministic embeddings remain the default; semantic embeddings
  require explicit provider selection and credentials.
- The runtime deliberately exposes allowlisted repository, test, and Git tools,
  not arbitrary shell execution.
- Recall@1 retains one observable miss. Top-k 3 and 5 satisfy the checked-in
  three-case retrieval fixture.
- Remote CI covers Ubuntu with Python 3.11 and 3.12; Windows Python 3.12 was
  validated locally.

Docs impact: major; provider setup, CLI workflow, evaluation metrics, quality
gates, roadmap, and acceptance evidence are synchronized.

## Unresolved Questions

None.
