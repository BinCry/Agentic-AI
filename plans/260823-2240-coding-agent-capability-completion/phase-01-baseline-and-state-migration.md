---
phase: 1
title: Baseline and State Migration
status: completed
effort: 2-3 days
dependsOn: []
---

# Phase 1: Baseline and State Migration

## Overview

Freeze a reproducible baseline, introduce explicit saved-state migration, and define capability budgets before changing execution behavior. This prevents later phases from making existing tasks unreadable and gives every capability a measurable safety/reliability gate.

## Requirements

- Preserve loading of every version-1 task fixture and reject unknown future versions with an actionable error.
- Migrations must be pure, ordered, idempotent at the current version, and backed up before the first write.
- Capture baseline unit, branch coverage, wheel smoke, read-only workflow, runtime-path, and local evaluation results without API keys.
- Define run-budget and model-usage value objects, but do not change orchestration behavior yet.
- All generated artifacts, backups, caches, and temporary files resolve under the workspace on D.

## Architecture

`JsonTaskStore.load()` reads raw JSON, sends it through `TaskStateMigrator`, then delegates strict validation to `CodingTaskState.from_dict()`. `CURRENT_TASK_SCHEMA_VERSION` has one owner. Version 2 adds typed, zero-default `run_budget` and `usage_ledger` fields so older tasks migrate without semantic change. A baseline command emits machine-readable metrics for later comparison.

## File Inventory

| Action | Path | Responsibility |
|---|---|---|
| Modify | `src/coding_agent/models/task_state.py` | Use shared schema version; persist typed budget/usage fields |
| Create | `src/coding_agent/models/run_accounting.py` | `RunBudget`, `UsageLedger`, validation, serialization |
| Create | `src/coding_agent/models/task_state_schema.py` | Single current/minimum schema-version owner |
| Create | `src/coding_agent/storage/task_state_migrations.py` | Ordered v1-to-v2 migration registry |
| Modify | `src/coding_agent/storage/task_store.py` | Backup, migrate, validate, atomic persistence |
| Modify | `src/coding_agent/storage/checkpoint_store.py` | Restore/list legacy checkpoints through the migration chain |
| Create | `src/coding_agent/evaluation/baseline*.py` | Versioned baseline orchestration and isolated quality gates |
| Create | `src/coding_agent/cli_baseline.py` | Narrow baseline CLI parser/handler |
| Modify | `src/coding_agent/cli.py` | Register `baseline` while preserving existing commands |
| Create | `tests/fixtures/task_states/version-1-task.json` | Golden compatibility fixture with no secrets |
| Create | `tests/test_task_state_migrations.py` | Migration and future-version rejection |
| Create | `tests/test_baseline.py` | Gate aggregation, optional tooling, metrics, CLI exit contract |
| Modify | `src/coding_agent/tools/repository_service.py`, `tests/test_repository_tools.py` | Correct ignore filtering for nested workspace roots |
| Update | `docs/reliability-and-recovery.md`, `docs/evaluation.md` | User-visible schema/recovery commands |

## Test Scenario Matrix

| Scenario | Expected result |
|---|---|
| Load v1 task | In-memory v2 state with zero usage/default budget and same workflow meaning |
| Load, save, reload migrated task | Exact stable v2 representation; backup created once |
| Load schema version 999 | Typed error; original file untouched |
| Interrupted atomic save | Last valid state remains loadable |
| Runtime roots configured on D | Baseline reports no task-owned path on C |
| Missing optional test tool | Baseline records unavailable gate, not a false pass |

## Interface Checklist

- `TaskStateMigrator.migrate(payload) -> dict[str, Any]`
- `RunBudget.from_dict()/to_dict()/validate()`
- `UsageLedger.record()/merge()/to_dict()` with non-negative counters
- `JsonTaskStore.load()` performs migration before model construction
- `coding-agent baseline --output <workspace-relative-path>` returns non-zero on required gate failure

## Implementation Steps

1. Add failing fixtures for v1 compatibility, unknown versions, interrupted save, and D-root accounting.
2. Extract the schema constant and implement pure ordered migrations plus atomic one-time backup.
3. Add typed run accounting with zero-default migration; keep providers/orchestrator behavior unchanged.
4. Add baseline collection and machine-readable output; record the verified starting values.
5. Update recovery/evaluation docs and run the full quality gate.

## Commit Boundaries

1. `test(state): capture saved-task compatibility contract`
2. `feat(state): add versioned task migration and accounting models`
3. `feat(evaluation): establish reproducible capability baseline`

## Success Criteria

- [x] All historical fixtures load, migrate, and round-trip deterministically.
- [x] Unknown future schemas cannot be silently rewritten.
- [x] Baseline JSON records test count, branch coverage, wheel smoke, runtime roots, and evaluation metrics.
- [x] Existing read-only and approval workflows remain behaviorally unchanged.
- [x] Full suite, branch coverage threshold, wheel smoke, and secret scan pass.

## Risks and Rollback

- Migration bugs can corrupt durable state. Mitigate with pure transforms, golden fixtures, atomic replace, and retained backup. Roll back by restoring the backup and prior package version.
- Do not store prompts or API keys in usage/accounting fields; only numeric usage and model/provider identifiers.
