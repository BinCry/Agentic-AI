---
phase: 4
title: "Enforce Reproducible Acceptance"
status: completed
priority: P1
effort: "2h"
dependencies: [3]
---

# Phase 4: Enforce Reproducible Acceptance

## Requirements

- Add a defensible line/branch coverage gate based on measured baseline.
- Add CI for supported Python versions with tests, coverage, packaging, and CLI smoke.
- Run retrieval, MCP/security, approval, recovery, end-to-end, packaging, and CLI gates.
- Update README/architecture/evaluation/demo docs from measured behavior only.
- Mark predecessor and completion plans complete only after all gates pass.

## Related Code Files

- Modify `pyproject.toml`.
- Create `.github/workflows/quality.yml`.
- Update relevant files under `docs/` and `README.md`.
- Create final reports under this plan's `reports/` directory.

## Implementation Steps

1. Add test extras and measured coverage threshold.
2. Add CI with no secrets and deterministic offline tests.
3. Run editable-install or wheel smoke inside a D: environment.
4. Execute all acceptance commands and record exact metrics.
5. Review for secrets, generated artifacts, stale claims, and grading labels.
6. Commit, push, and verify local/remote SHA.

## Tests and Acceptance

- [x] CI-equivalent local gates pass.
- [x] Coverage report includes measured line and branch values.
- [x] Retrieval report includes Recall@1/3/5, MRR, citation correctness, latency, failures.
- [x] README demo commands match the installed CLI.
- [x] Working tree is clean except intentional local-only Codex configuration.

## Completion Evidence

- Quality implementation: `c7ec9cb7a173b11a9edcbc9352522e0adf6e48ad`.
- Cross-platform assertion fix: `0396b12d773225904a4b3666743881ba54c1b950`.
- Full local suite: 131 passed; combined branch coverage: 82% against an 80% gate.
- GitHub Actions run `32583019842`: Python 3.11 and 3.12 jobs passed coverage,
  wheel build, installed-wheel import, and CLI smoke.
- Retrieval top-k 1/3/5 results are recorded in `docs/evaluation.md`; citation
  correctness remained 1.0 and top-k 3/5 had no failures.
- Final acceptance details: `reports/final-260822-coding-agent-acceptance.md`.

## Risk and Rollback

- Gate too high can create brittle incentives; set from measured critical-path coverage.
- Roll back only the threshold, not tests or correctness fixes, if platform variance is proven.
