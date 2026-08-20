# Phase 01: Core Task State and Workflow

## Context Links

- Plan: [plan.md](./plan.md)
- Previous phase: [phase-00-repository-audit-and-restructure.md](./phase-00-repository-audit-and-restructure.md)

## Overview

- **Priority:** high
- **Status:** completed
- **Description:** Build the typed task state, workflow engine, skill routing, structured-output boundary, persistence, and trace foundation.

## Requirements

### Functional

- Implement all required workflow states and explicit transitions.
- Persist `CodingTaskState` outside conversation history.
- Route existing skills by workflow state.
- Validate structured LLM outputs with bounded retry metadata.
- Record append-only trace events without secrets.

### Non-functional

- Standard-library-first Python design with no cloud dependency.
- Every writable path must remain under the configured runtime root.
- Unit test invalid transitions, serialization, routing, validation, and path policy.

## Related Code Files

- **Create:** `pyproject.toml`, `src/coding_agent/`, `tests/`, `docs/`
- **Modify:** `README.md`
- **Delete:** none

## Implementation Steps

1. Define task, evidence, plan, test, review, checkpoint, and trace models.
2. Implement transition policy and bounded workflow controller.
3. Load and route existing skill definitions by state.
4. Add structured-output validation and JSON task persistence.
5. Add tests and architecture documentation.

## Todo

- [x] Define typed state and structured decision models.
- [x] Implement state machine and retry bounds.
- [x] Implement skill catalog and router.
- [x] Implement workspace-scoped persistence and trace.
- [x] Add unit tests and documentation.

## Success Criteria

- All Phase 01 tests pass with no writes outside a D-based temporary workspace.
- Invalid transitions and invalid structured outputs fail explicitly.

## Risk Assessment

| Risk | Impact | Mitigation |
|---|---|---|
| Skill mirror drift changes prompts | medium | Store selected skill path and content digest in task state |
| State corruption | high | Atomic JSON writes and schema versioning |
| Infinite workflow loop | high | Enforce iteration and repair limits in state transitions |

## Next Steps

- Expose the controlled repository operations through MCP in Phase 02.
