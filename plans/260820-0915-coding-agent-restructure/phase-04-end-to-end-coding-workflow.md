# Phase 04: End-to-End Coding Workflow

## Context Links

- Plan: [plan.md](./plan.md)

## Overview

- **Priority:** high
- **Status:** completed
- **Description:** Connect analysis, retrieval, planning, editing, testing, debugging, review, and summary.

## Requirements

- One main orchestrator with state-selected reusable skills.
- Structured plans and review results grounded in repository evidence.
- Targeted tests before broader regression tests.
- Final diff and PR summary with citations.

## Todo

- [x] Implement observe/decide/execute/validate loop.
- [x] Connect RAG, controlled tools, approvals, and persisted task state.
- [x] Implement bounded repair loop and final review gate.
- [x] Add a deterministic end-to-end fixture repository.

## Success Criteria

- A fixture issue completes with passing tests, a grounded diff, trace metadata,
  and repository citations.

## Delivered

- `src/coding_agent/workflow/orchestrator.py` implements the bounded state-selected loop.
- `PromptAssembler` keeps model context bounded and source-grounded.
- `repo.retrieve` evidence is persisted and required for patch mutations.
- `fixture` is an allowlisted test profile for deterministic E2E validation.
- Windows path resolution and raw-byte SHA-256 checks keep evidence and patches
  consistent across newline formats.

## Verification

- Full suite: 71 tests passed, 2 Windows symlink tests skipped because symlink
  privilege is unavailable to the current account.

## Risk Assessment

| Risk | Impact | Mitigation |
|---|---|---|
| Ungrounded edit | high | Require exact-source read before mutation |

## Next Steps

- Harden retries, approvals, checkpoints, and recovery.
