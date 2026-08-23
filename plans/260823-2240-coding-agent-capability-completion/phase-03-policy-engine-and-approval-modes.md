---
phase: 3
title: "Policy Engine and Approval Modes"
status: completed
effort: "4-5 days"
dependsOn: [1, 2]
---

# Phase 3: Policy Engine and Approval Modes

## Overview

Replace the fixed tool-spec decision with a layered, inspectable policy engine while retaining current tool validation. This phase establishes authority boundaries before general command execution exists.

## Requirements

- Decisions are exactly `allow`, `deny`, or `ask`; deny takes precedence and built-in invariants cannot be overridden.
- Match typed tool name, argument predicates, workspace mode, and command prefix; never evaluate code from policy files.
- Support `read-only`, `ask`, and `auto-edit` modes. `auto-edit` permits bounded workspace edits only, never remote or destructive effects.
- Track workspace trust separately from approval mode; approval never implies process isolation.
- Policy layers: immutable built-ins, explicitly supplied trusted file, workspace narrowing rules, and session mode.
- Add a `policy check` explanation command and redact secrets from decisions/events.

## Architecture

Move general rule models/compilation into `coding_agent.policy`. Keep `ToolPermissionPolicy` as the compatibility adapter for `ToolExecutor`. Compile layers into an ordered immutable rule set. Each `PolicyDecision` includes rule id, layer, reason code, and approval requirement, enabling tests and later event streaming.

## File Inventory

| Action | Path | Responsibility |
|---|---|---|
| Create | `src/coding_agent/policy/__init__.py` | Public policy contracts |
| Create | `src/coding_agent/policy/models.py` | Rule, matcher, layer, mode, decision types |
| Create | `src/coding_agent/policy/loader.py` | Strict TOML loading and workspace narrowing validation |
| Create | `src/coding_agent/policy/engine.py` | Deterministic precedence and explanation |
| Modify | `src/coding_agent/tools/policy.py` | Compatibility adapter and path/argument validators |
| Modify | `src/coding_agent/tools/contracts.py` | Risk/effect metadata on tool specs |
| Modify | `src/coding_agent/tools/executor.py` | Consume explained decisions; preserve approval durability |
| Modify | `src/coding_agent/workflow/runtime.py` | Build layered policy from explicit CLI inputs |
| Modify | `src/coding_agent/cli.py` | Add mode/policy flags and `policy check`; extract parser groups |
| Create | `tests/fixtures/policies/*.toml` | Allow/deny/ask and invalid rule fixtures |
| Create | `tests/test_policy_engine.py` | Precedence, explanation, redaction, mode matrix |
| Modify | `tests/test_tool_policy.py`, `tests/test_tool_executor.py`, `tests/test_cli.py` | Compatibility and approval regression |
| Update | `docs/testing-and-safety.md`, `docs/controlled-mcp-tools.md` | Trust layers and user commands |

## Test Scenario Matrix

| Scenario | Expected result |
|---|---|
| Trusted allow conflicts with built-in deny | Deny with immutable-rule explanation |
| Workspace rule attempts to widen permission | Configuration rejected |
| Read-only mode receives write tool | Deny before model/tool execution |
| Ask mode receives bounded edit | Durable approval request |
| Auto-edit receives bounded workspace patch | Allow; checkpoint still required |
| Any mode receives network/push/destructive request | Ask or deny, never implicit allow |
| Untrusted workspace requests local process | Deny unless a configured execution boundary can isolate it |
| Secret-like argument/environment | Redacted in explanation and traces |

## Interface Checklist

- `PolicyEngine.evaluate(PolicyInput) -> PolicyDecision`
- `PolicyLoader.load_explicit(path)` and `load_workspace_narrowing(path)`
- `PolicyDecision` carries stable reason code and matched rule id
- `ToolRisk` separates read, workspace-write, destructive, process, network, and remote-write effects
- `WorkspaceTrust` is explicit and independent from `ApprovalMode`
- `policy check --tool ... --arguments-json ... --mode ...` never executes a tool

## Implementation Steps

1. Write precedence, mode, invalid-config, and redaction tests around existing tools.
2. Implement typed rules and strict loader with no executable expressions.
3. Adapt current tool policy/executor while preserving all existing decisions.
4. Expose CLI explanation and document trust/approval semantics.
5. Run approval, recovery, read-only, MCP-server, and full regression suites.

## Commit Boundaries

1. `test(policy): define layered authority and approval modes`
2. `feat(policy): add deterministic layered policy engine`
3. `refactor(tools): route permissions through explained policy`
4. `feat(cli): expose policy checks and execution modes`

## Success Criteria

- [x] Existing tool requests retain or reduce their previous authority.
- [x] Every policy result is deterministic, explained, redacted, and serializable.
- [x] Workspace configuration cannot weaken built-in path, drive, read-only, or remote-effect restrictions.
- [x] `policy check` covers all registered tools without side effects.
- [x] Negative security matrix and full quality gate pass.

## Risks and Rollback

- Flexible matching can become an accidental policy language. Limit predicates to typed equality/prefix/path/effect operators and reject unknown keys.
- Maintain the previous `ToolPermissionPolicy` facade so the new engine can be disabled without changing tool contracts.
