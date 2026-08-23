---
phase: 8
title: "Git Delivery Workflow"
status: pending
effort: "4-6 days"
dependsOn: [3, 4, 5, 6]
---

# Phase 8: Git Delivery Workflow

## Overview

Add a controlled local Git delivery workflow: branch/worktree preparation, exact-path staging, commit creation, and optional push. Git mutation is separate from code editing, fully observable, and always bounded by repository state and explicit authority.

## Requirements

- Preserve existing status/diff/changed-files tools and add typed branch, worktree, stage, commit, and push operations.
- Stage only exact reviewed paths; reject secrets, ignored files, nested repositories, unresolved conflicts, and changes outside the approved set.
- Local branch/commit operations require workspace-write authority. Push is a remote write and always requires explicit approval for the exact remote/ref.
- Never support force push, history rewrite, broad clean/reset, arbitrary Git config mutation, or automatic author identity rotation.
- Use existing repository-local Git identity at execution time and report it before commit; missing identity produces an actionable stop.

## Architecture

Extend `GitService` with typed request models, each mapped to a fixed argv template rather than generic Git strings. `DeliveryService` computes a manifest (base/head, files, diff digest, tests, author, target), asks policy/approval, then performs one idempotent step. Worktrees live under an explicit D-drive root and are verified before creation/removal.

## File Inventory

| Action | Path | Responsibility |
|---|---|---|
| Create | `src/coding_agent/delivery/__init__.py` | Public delivery contracts |
| Create | `src/coding_agent/delivery/models.py` | Branch/worktree/stage/commit/push request and manifest |
| Create | `src/coding_agent/delivery/service.py` | Sequenced idempotent delivery operations |
| Modify | `src/coding_agent/tools/git_service.py` | Fixed argv Git primitives and state verification |
| Modify | `src/coding_agent/tools/contracts.py`, `policy.py`, `executor.py` | Git effect/risk registration and approvals |
| Modify | `src/coding_agent/models/task_state.py` | Delivery manifest/result references |
| Modify | `src/coding_agent/events/models.py` | Git lifecycle and remote-write events |
| Modify | `src/coding_agent/cli.py` | `deliver prepare|commit|push|status` commands |
| Create | `tests/fixtures/git/` | Runtime-created local bare/working repositories on D temp root |
| Create | `tests/test_git_delivery.py`, `tests/test_git_security.py` | Exact staging, identity, conflict, push authority |
| Modify | `tests/test_repository_tools.py`, `tests/test_tool_executor.py`, `tests/test_cli.py` | Compatibility/integration |
| Update | `docs/end-to-end-workflow.md`, `docs/testing-and-safety.md` | Delivery and approval behavior |

## Test Scenario Matrix

| Scenario | Expected result |
|---|---|
| Prepare branch/worktree under approved D root | Created with verified base and durable manifest |
| User/unrelated dirty files present | Preserved and excluded; conflicting requested path stops |
| Stage exact reviewed files | Index contains exactly manifest paths |
| Secret scanner flags a staged file | Commit blocked; index/worktree preserved for review |
| Missing/conflicting Git identity | Stop and report; no config changed automatically |
| Commit retried after crash | Existing matching commit recognized; no duplicate commit |
| Push without exact approval | Pending approval; no network operation |
| Force/ref rewrite request | Immutable denial |

## Interface Checklist

- `DeliveryManifest` records repository, base/head, paths, diff digest, verification evidence, author, remote/ref
- `GitService` methods build fixed argv internally; callers cannot supply raw subcommands
- `DeliveryService.prepare()/stage()/commit()/push()` are separately idempotent
- `push()` verifies approval binds remote URL identity, source SHA, and destination ref
- Worktree deletion is not part of automatic success cleanup; recovery remains possible

## Implementation Steps

1. Add local-repository tests for dirty state, exact staging, identity, secrets, crash retry, and push approval.
2. Extend fixed Git primitives and register their policy effects.
3. Implement delivery manifest/service with checkpoint and event integration.
4. Add CLI workflow and documentation; validate current user changes remain untouched.
5. Run local bare-remote integration tests, full suite, wheel smoke, and secret scan.

## Commit Boundaries

1. `test(git): define controlled delivery safety contract`
2. `feat(git): add exact local branch stage and commit operations`
3. `feat(delivery): add approved idempotent push workflow`
4. `feat(cli): expose delivery lifecycle`

## Success Criteria

- [ ] Unrelated/dirty user files are never staged, overwritten, reset, or removed.
- [ ] Commit content exactly matches the reviewed manifest and passed verification evidence.
- [ ] Push cannot occur without approval bound to the exact SHA/remote/ref.
- [ ] Force, rewrite, broad cleanup, and automatic identity mutation are impossible through registered tools.
- [ ] Crash/retry does not duplicate commits or pushes.

## Risks and Rollback

- Git actions affect attribution and remote history. Keep author identity explicit/reported and remote writes human-approved; do not encode identity rotation in product code.
- Worktree cleanup can be destructive. Leave cleanup manual until path-validation and recovery evidence justify a separate approved operation.
