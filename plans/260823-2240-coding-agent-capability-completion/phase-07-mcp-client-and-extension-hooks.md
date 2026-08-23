---
phase: 7
title: "MCP Client and Extension Hooks"
status: pending
effort: "5-7 days"
dependsOn: [3, 5, 6]
---

# Phase 7: MCP Client and Extension Hooks

## Overview

Let the agent consume external tools through a minimal MCP stdio client and declarative extension hooks. Keep the existing MCP server intact. Remote HTTP/SSE/OAuth transports remain conditional until local trust, event, timeout, and approval behavior is proven.

## Requirements

- Implement MCP initialize, capability negotiation, tool listing, tool calling, cancellation/timeout, and clean shutdown over stdio JSON-RPC.
- Configuration is explicit and trusted; workspace files may only narrow an already declared server/tool allowlist.
- Sanitize child environment, resolve executables under Phase 4 policy, bound schemas/results, and route every call through Phase 3 authority.
- Namespaced discovered tools cannot shadow built-ins; server/tool identity is durable in events and observations.
- Extension hooks are declarative, time-bounded, failure-isolated, and cannot mutate decisions directly.

## Architecture

`McpClientSession` owns one stdio subprocess and JSON-RPC request map. `McpRegistry` converts remote tool metadata into namespaced `ToolSpec` adapters after schema validation. `ExtensionManifest` declares capabilities and hook commands; `HookRunner` emits bounded advisory input/output events. The normal policy/executor/observation path remains the only route into the workflow.

## File Inventory

| Action | Path | Responsibility |
|---|---|---|
| Create | `src/coding_agent/mcp/client.py` | Stdio lifecycle and JSON-RPC correlation |
| Create | `src/coding_agent/mcp/registry.py` | Discovery, namespacing, schema limits, tool adapters |
| Create | `src/coding_agent/mcp/config.py` | Strict trusted server configuration and secret references |
| Create | `src/coding_agent/extensions/manifest.py` | Declarative capability/hook manifest |
| Create | `src/coding_agent/extensions/__init__.py` | Public extension contracts |
| Create | `src/coding_agent/extensions/hooks.py` | Policy-governed bounded hook execution |
| Modify | `src/coding_agent/tools/contracts.py`, `executor.py` | Dynamic registered specs through same policy path |
| Modify | `src/coding_agent/events/models.py` | MCP/hook lifecycle events |
| Modify | `src/coding_agent/cli.py` | `mcp list/status/test` and explicit config flags |
| Preserve | `src/coding_agent/mcp/server.py` | Existing server behavior and compatibility |
| Create | `tests/fixtures/mcp/stdio_test_server.py` | Offline protocol fixture, no network |
| Create | `tests/test_mcp_client.py`, `tests/test_mcp_registry.py`, `tests/test_extension_hooks.py` | Lifecycle/trust/isolation contracts |
| Modify | `tests/test_mcp_server.py`, `tests/test_tool_executor.py`, `tests/test_cli.py` | Regression/integration |
| Update | `docs/controlled-mcp-tools.md`, `docs/system-architecture.md` | Client trust and extension boundaries |

## Test Scenario Matrix

| Scenario | Expected result |
|---|---|
| Valid stdio server | Initialize/list/call/shutdown succeeds with correlated events |
| Server hangs or emits oversized/invalid JSON | Timeout/terminate; bounded diagnostic; workflow survives |
| Remote name collides with built-in | Namespaced or rejected; built-in unchanged |
| Workspace config adds undeclared server/tool | Rejected as permission widening |
| Server asks for secret environment | Only explicit named reference injected; value never logged/persisted |
| MCP tool has write/network effect | Same ask/deny policy and durable approval as local tool |
| Hook exits non-zero or mutates files | Failure isolated; undeclared mutation blocked/detected |

## Interface Checklist

- `McpClientSession.initialize()/list_tools()/call_tool()/cancel()/close()`
- `McpRegistry.register(server_id, definitions) -> tuple[ToolSpec, ...]`
- Tool namespace format is stable and collision-safe
- `McpServerConfig` stores secret variable names, never secret values
- `HookRunner.run(hook_point, context)` returns advisory bounded result only

## Implementation Steps

1. Add offline stdio protocol, malformed-server, timeout, collision, and secret-redaction tests.
2. Implement client lifecycle and registry with strict schema/result quotas.
3. Route MCP calls through policy, approvals, observations, and events.
4. Add declarative manifests/hooks and explicit CLI diagnostics.
5. Re-run MCP server compatibility and full security/recovery gates.

## Commit Boundaries

1. `test(mcp): define client trust and lifecycle contracts`
2. `feat(mcp): add policy-governed stdio client`
3. `feat(extensions): add declarative bounded hooks`
4. `feat(cli): expose MCP diagnostics`

## Success Criteria

- [ ] Offline MCP fixture completes discovery/call/cancel/shutdown deterministically.
- [ ] Remote tools never bypass local policy, approvals, quotas, observations, or events.
- [ ] Malformed/hung servers cannot hang or corrupt the workflow.
- [ ] Secrets are referenced, not stored or emitted.
- [ ] Existing MCP server tests and public behavior remain compatible.

## Risks and Rollback

- MCP expands the trust boundary to arbitrary subprocesses. Require explicit configuration and default-deny tools; document that approval is not a sandbox.
- Defer HTTP/SSE/OAuth until stdio metrics justify the additional network/token-storage surface.
