---
phase: 4
title: "Enforce Reproducible Acceptance"
status: pending
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

- [ ] CI-equivalent local gates pass.
- [ ] Coverage report includes measured line and branch values.
- [ ] Retrieval report includes Recall@1/3/5, MRR, citation correctness, latency, failures.
- [ ] README demo commands match the installed CLI.
- [ ] Working tree is clean except intentional local-only Codex configuration.

## Risk and Rollback

- Gate too high can create brittle incentives; set from measured critical-path coverage.
- Roll back only the threshold, not tests or correctness fixes, if platform variance is proven.
