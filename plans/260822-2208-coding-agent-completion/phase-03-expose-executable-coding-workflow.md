---
phase: 3
title: "Expose Executable Coding Workflow"
status: pending
priority: P1
effort: "3h"
dependencies: [2]
---

# Phase 3: Expose Executable Coding Workflow

## Requirements

- Add a CLI command that starts or resumes `CodingWorkflowOrchestrator`.
- Configure the production provider without accepting secrets as CLI arguments.
- Preserve approval pauses by default; allow automation only through an explicit flag.
- Persist state after each step and return stable JSON/exit codes.
- Keep tool policy, workspace containment, test allowlist, and completion invariants intact.

## Related Code Files

- Modify `src/coding_agent/cli.py` or extract a focused runtime builder if needed.
- Modify package exports and CLI tests.
- Add an offline end-to-end CLI fixture using an injected/replay transport only in tests.
- Update user workflow documentation.

## Implementation Steps

1. Add provider/runtime configuration parsing.
2. Build executor, skill router, provider, and orchestrator from existing components.
3. Implement new-task and resume paths with approval-safe defaults.
4. Add JSON results for terminal, waiting-approval, configuration-error, and failure states.
5. Verify end-to-end issue analysis through final report in an offline fixture.

## Tests and Acceptance

- [ ] CLI runs and resumes the real orchestrator boundary.
- [ ] Missing key, invalid provider response, approval pause, and terminal success are tested.
- [ ] Default invocation cannot silently auto-approve mutation or test tools.
- [ ] Existing CLI contracts remain compatible.

## Risk and Rollback

- CLI growth may exceed maintainable size; extract only cohesive runtime construction.
- Rollback leaves existing state/MCP/evaluation commands untouched.
