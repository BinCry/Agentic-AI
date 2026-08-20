# Phase 00: Repository Audit and Safe Restructure

## Context Links

- Plan: [plan.md](./plan.md)
- Source instructions: [../../AGENTS.md](../../AGENTS.md)

## Overview

- **Priority:** high
- **Status:** completed
- **Description:** Establish a clean, trackable project layout without removing supported client contracts.

## Requirements

### Functional

- Preserve `.claude`, `.codex`, and existing client adapters.
- Remove tracked dependency installs, coverage output, Python bytecode, and backup artifacts.
- Add reproducible dependency metadata before removing bundled installs.
- Create `src/`, `tests/`, `docs/`, and benchmark-ready project structure.

### Non-functional

- Resolve and validate every recursive deletion under `D:\Agentic-AI`.
- Keep the working tree auditable through Git.

## Related Code Files

- **Modify:** `.gitignore`, `.repomixignore`, `README.md`
- **Create:** `pyproject.toml`, `docs/*`, `src/coding_agent/*`, `tests/*`
- **Delete:** nested `node_modules`, coverage artifacts, bytecode, `.gemini/*.bak`

## Implementation Steps

1. Record baseline architecture, mirror drift, disk use, and tests.
2. Make plans and dependency locks trackable.
3. Add missing lock metadata, then remove generated dependency trees.
4. Verify retained package manifests and client entry contracts.

## Todo

- [x] Audit repository structure and reusable components.
- [x] Run safe D-only baseline tests.
- [x] Remove generated/vendor artifacts after lock verification.
- [x] Create the target source, test, and documentation structure.
- [x] Verify Git diff and retained client files.

## Success Criteria

- Generated artifacts are removed without deleting client-specific source.
- New project artifacts are tracked and no test writes to `C:`.

## Risk Assessment

| Risk | Impact | Mitigation |
|---|---|---|
| Mirror removal breaks clients | high | Keep client roots in this phase |
| Dependency reinstall becomes non-reproducible | high | Generate or preserve lockfiles before cleanup |
| Default home/temp touches `C:` | high | Override and validate all writable roots |

## Next Steps

- Implement Phase 01 only after the restructure verifies cleanly.
