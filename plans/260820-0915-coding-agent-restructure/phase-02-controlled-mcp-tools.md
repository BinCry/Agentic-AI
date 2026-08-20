# Phase 02: Controlled MCP Tools

## Context Links

- Plan: [plan.md](./plan.md)

## Overview

- **Priority:** high
- **Status:** pending
- **Description:** Expose validated repository, patch, test, and Git tools through MCP.

## Requirements

- Workspace path containment and traversal prevention.
- Typed tool inputs, outputs, errors, timeouts, logs, and output limits.
- Read/search/symbol, patch/create, approved tests, and Git status/diff tools.
- No arbitrary destructive shell command exposed to the model.

## Todo

- [ ] Define MCP contracts and permission policy.
- [ ] Implement repository and mutation services.
- [ ] Implement test and Git allowlists.
- [ ] Add MCP transport and contract tests.

## Success Criteria

- Traversal, forbidden commands, timeouts, and patch conflicts are tested.

## Risk Assessment

| Risk | Impact | Mitigation |
|---|---|---|
| Tool privilege escalation | high | Deny by default and validate resolved paths |

## Next Steps

- Build retrieval over the same repository boundary.
