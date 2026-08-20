# Phase 02: Controlled MCP Tools

## Context Links

- Plan: [plan.md](./plan.md)

## Overview

- **Priority:** high
- **Status:** completed
- **Description:** Expose validated repository, patch, test, and Git tools through MCP.

## Requirements

- Workspace path containment and traversal prevention.
- Typed tool inputs, outputs, errors, timeouts, logs, and output limits.
- Read/search/symbol, patch/create, approved tests, and Git status/diff tools.
- No arbitrary destructive shell command exposed to the model.

## Todo

- [x] Define MCP contracts and permission policy.
- [x] Implement repository and mutation services.
- [x] Implement test and Git allowlists.
- [x] Add MCP transport and contract tests.

## Success Criteria

- Traversal, forbidden tools/arguments, timeouts, output limits, and patch conflicts are tested.
- Mutating tools are bound to an exact approval request and arguments hash.
- MCP `initialize`, `tools/list`, `tools/call`, and stdio notification handling are covered by contract tests.

## Risk Assessment

| Risk | Impact | Mitigation |
|---|---|---|
| Tool privilege escalation | high | Deny by default and validate resolved paths |

## Next Steps

- Build retrieval over the same repository boundary in Phase 3.

## Delivered Modules

- `src/coding_agent/tools/contracts.py`: typed tool requests, results, specs, and pending approvals.
- `src/coding_agent/tools/policy.py`: deny-by-default tool/state/path/argument policy.
- `src/coding_agent/tools/repository_service.py`: bounded UTF-8 read, exact search, and Python symbols.
- `src/coding_agent/tools/patch_service.py`: create and conflict-aware unified patch operations.
- `src/coding_agent/tools/test_runner.py` and `git_service.py`: named test profiles and read-only Git.
- `src/coding_agent/tools/executor.py`: controller-owned approval, dispatch, state updates, and trace metadata.
- `src/coding_agent/mcp/server.py`: dependency-free JSON-RPC stdio transport.
- CLI commands: `mcp-server` and `approve-tool`.

## Verification

- Full regression and Phase 2 contract suite: 65 tests passed; 2 Windows symlink tests skipped because the current account lacks symlink privilege.
- No arbitrary shell command is exposed; subprocess calls use fixed allowlists, `shell=False`, bounded output, and timeout process-tree termination.
