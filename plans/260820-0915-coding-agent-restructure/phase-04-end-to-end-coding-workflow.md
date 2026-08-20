# Phase 04: End-to-End Coding Workflow

## Context Links

- Plan: [plan.md](./plan.md)

## Overview

- **Priority:** high
- **Status:** pending
- **Description:** Connect analysis, retrieval, planning, editing, testing, debugging, review, and summary.

## Requirements

- One main orchestrator with state-selected reusable skills.
- Structured plans and review results grounded in repository evidence.
- Targeted tests before broader regression tests.
- Final diff and PR summary with citations.

## Todo

- [ ] Implement observe/decide/execute/validate loop.
- [ ] Connect skills, RAG, MCP tools, and state persistence.
- [ ] Implement repair loop and final review gate.
- [ ] Add an end-to-end fixture repository.

## Success Criteria

- A benchmark issue completes with passing tests, diff, trace, and citations.

## Risk Assessment

| Risk | Impact | Mitigation |
|---|---|---|
| Ungrounded edit | high | Require exact-source read before mutation |

## Next Steps

- Harden retries, approvals, checkpoints, and recovery.
