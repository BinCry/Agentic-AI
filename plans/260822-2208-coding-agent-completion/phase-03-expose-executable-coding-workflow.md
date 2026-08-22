---
phase: 3
title: "Expose Executable Coding Workflow"
status: completed
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

- [x] CLI starts and resumes the real orchestrator boundary.
- [x] Missing key, invalid provider output, approval pause, external approval,
  persisted failure, and terminal success tested offline.
- [x] Default invocation pauses mutation/test; automation requires `--auto-approve`.
- [x] Existing CLI commands and legacy pending states remain compatible.

## Completion Evidence

- Implementation commit: `5640007035ed02760ab5591b0741d4791ab8d2dc`.
- Full suite: 131 passed; combined branch coverage 82%.
- CLI help exposes no credential argument.
- Local and `origin/main` SHA matched after push.
- Report: [Phase 3 Executable Workflow](./reports/phase-03-executable-workflow-report.md).

## Risk and Rollback

- CLI growth may exceed maintainable size; extract only cohesive runtime construction.
- Rollback leaves existing state/MCP/evaluation commands untouched.
