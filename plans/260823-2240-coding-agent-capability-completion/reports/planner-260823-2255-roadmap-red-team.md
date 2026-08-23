# Roadmap Red-Team Review

## Result

PASS after scope and safety corrections. The roadmap is executable in sequential capability slices and does not require copying another agent architecture.

## Checks

| Check | Finding | Resolution |
|---|---|---|
| Existing-plan overlap | All three prior plans are complete | New plan has no `blockedBy` dependency |
| Feature-parity bias | Original ambition could grow into gateway/TUI/multi-agent scope | Explicitly deferred; measured gaps only |
| Execution isolation | `shell=False` prevents shell parsing but does not sandbox repository code | Added workspace trust separate from approval; untrusted local process denied without isolation boundary |
| Durable compatibility | Later fields/events could break version-1 tasks | Phase 1 owns ordered migration, backup, golden fixture, and unknown-version rejection |
| Tool-loop autonomy | Iteration could bypass state/approval or repeat mutations | Outer state machine remains authoritative; budgets, idempotency, and persisted observations required |
| Context leakage | Streaming/events could persist prompts, reasoning, secrets, or large output | Versioned redacted envelopes; safe summaries/digests only |
| MCP trust | MCP server process and discovered tools expand execution authority | Explicit trusted config, environment sanitization, namespacing, normal policy/approval path |
| Git damage | Broad stage/reset/force/push or implicit identity changes can affect user work/attribution | Exact-path staging, no rewrite/force/clean, exact remote approval, identity read/report only |
| Benchmark disk risk | Docker/SWE-bench may write large artifacts to full C drive | Optional late lane; hard-fail until all container/cache/temp roots resolve to D |
| False quality claim | Offline scripted fixtures can validate harness but not agent quality | Separate harness correctness from repeated bounded live-provider results |
| Module growth | `cli.py`, `orchestrator.py`, and `executor.py` already carry many responsibilities | Phase-owned extraction boundaries included; no unrelated bulk rewrite |

## Consistency Sweep

- Nine phase files exist, have explicit effort/dependencies, and link from `plan.md`.
- Dependencies are acyclic and every cross-phase type is introduced before use.
- Every phase includes requirements, architecture, file inventory, scenario matrix, interface checklist, implementation order, commit boundaries, success criteria, and rollback notes.
- Existing public contracts have compatibility paths: `ToolPermissionPolicy`, `test.run`, MCP server, JSON CLI, traces, saved tasks.
- Every mutating or remote capability has a negative test and recovery/idempotency expectation.
- `ck plan validate --strict --json` passed with zero issues; all local Markdown links resolve; no scaffold placeholders remain.

## Scope Decision

Selected: evolve current Python core through measured capability slices.

Deferred: multi-agent/subagent orchestration, OpenClaw-style messaging gateway, Agent Canvas/cloud control plane, rich TUI, browser/computer-use, unrestricted shell, remote MCP transport, and external benchmark containers before D-root verification.

## Unresolved Questions

None blocking Phase 1. Container sandbox implementation and remote MCP transports require later metric-based decisions; their interfaces are planned without promising those backends now.
