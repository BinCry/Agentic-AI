# Phase 06 Evaluation Report

## Scope

The report covers the deterministic retrieval smoke benchmark and the
machine-readable metrics emitted by `coding-agent evaluate`. No external LLM,
network service or fabricated task outcome is used.

## Measured run

Command:

```powershell
python -B -m coding_agent --workspace D:\Agentic-AI evaluate `
  --benchmark tests/fixtures/benchmarks/retrieval_cases.json `
  --top-k 5
```

Observed output summary:

| Metric | Result |
|---|---:|
| Retrieval cases | 3 |
| Recall@5 | 1.0 |
| MRR | 0.8333 |
| Citation correctness | 1.0 |
| Coding-agent task samples | 0 |

The zero coding-agent sample count is intentional: no persisted task IDs were
passed to this retrieval-only run. Completion, issue-resolution, repair,
average-repair-attempt, test, regression, tool-failure and invalid-tool-call
rates were emitted as `null`, not estimated.

The benchmark cases now carry the issue, expected files, acceptance criteria
and expected tests needed to connect retrieval evidence to an auditable coding
task. Task-state reports also enforce final diff, PR summary and final citation
fields before `COMPLETED`.

## Failure analysis

The repository-wide regression run after the checklist additions passed 83 tests;
2 Windows symlink tests were skipped because the current account lacks symlink
privilege.

Each benchmark case reports retrieved paths, relevant paths, latency and a
failure object. The Phase 6 verification run had no missing-relevant or
ungrounded-citation failures. Future benchmark runs should attach their JSON
output to the experiment record rather than replacing a failure with a pass.
