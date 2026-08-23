# Phase 1 Completion: Baseline and State Migration

## Status

Completed 2026-08-23. Roadmap progress: 1/9 phases (11%).

## Delivered

| Capability | Evidence |
|---|---|
| Saved-state schema v2 | Pure v1-to-v2 migration; strict future-version rejection |
| Recovery protection | Exact legacy bytes backed up once before first migrated save |
| Checkpoint compatibility | Restore/list paths use same migration chain |
| Run accounting | Validated zero-default `RunBudget` and aggregate `UsageLedger` |
| Baseline CLI | Unit, read-only, coverage, wheel, runtime-drive, retrieval gates |
| Path-filter fix | Ignore names evaluated relative to workspace, not absolute ancestors |

## Verification

| Gate | Result |
|---|---|
| Unit | 164/164 passed |
| Branch coverage | 82.49%; minimum 80% |
| Wheel | build + isolated install + import `0.1.0` passed |
| Read-only workflow | passed without mutation/test execution |
| Retrieval | recall@5 1.0; citation correctness 1.0 |
| Runtime paths | no writable path on C |
| Secret scan | no high-confidence secret found in staged changes |

## Review

- Fixed invalid usage counters raising `TypeError` before typed validation.
- Fixed repository ignore filtering when workspace ancestors use an ignored name.
- No API keys, prompts, private reasoning, or raw process output stored in baseline report.
- Existing CLI, approval, recovery, MCP server, and task-state round trips covered by full regression suite.

## Commits

- `4ad246f` — saved-task compatibility tests.
- `475939a` — schema migration, immutable backup, checkpoint support, accounting.
- Baseline/docs slice committed with this report.

## Next

Phase 2: scoped instruction hierarchy and Python/Node project discovery.

## Unresolved Questions

None.
