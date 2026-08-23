---
title: Production Coding Agent Capability Completion
description: >-
  Incrementally close verified coding-agent gaps without replacing the durable
  Python core.
status: in-progress
priority: P1
branch: main
tags:
  - coding-agent
  - safety
  - execution
  - context
  - mcp
  - evaluation
blockedBy: []
blocks: []
created: '2026-08-23T15:43:12.311Z'
createdBy: 'ck:plan'
source: skill
---

# Production Coding Agent Capability Completion

## Overview

Upgrade the current durable, approval-aware Python agent into a practical coding agent. Reference proven ideas from Gemini CLI, Codex, OpenHands SDK, OpenClaw, SWE-agent, SWE-bench, and Terminal-Bench, then adapt only capabilities justified by a repository gap and an acceptance test.

Scope is intentionally narrower than feature parity: retain the current state machine, evidence grounding, RAG, checkpoint, provider, and workspace-safety contracts. Build a safe command layer, project instruction discovery, iterative tool loop, observable sessions, MCP client, controlled Git delivery, and realistic evaluation. Multi-agent orchestration, messaging gateways, rich TUI, cloud control planes, browser automation, and unrestricted shell execution remain out of scope.

Research and gap matrix: [official coding-agent capability study](./research/official-coding-agent-capability-study.md).

Progress: 1/9 phases completed (11%). Phase 2 is next.

## Phases

| Phase | Name | Status |
|-------|------|--------|
| 1 | [Baseline and State Migration](./phase-01-baseline-and-state-migration.md) | Completed |
| 2 | [Instruction Hierarchy and Project Discovery](./phase-02-instruction-hierarchy-and-project-discovery.md) | Pending |
| 3 | [Policy Engine and Approval Modes](./phase-03-policy-engine-and-approval-modes.md) | Pending |
| 4 | [Safe Command and Test Harness](./phase-04-safe-command-and-test-harness.md) | Pending |
| 5 | [Iterative Tool Loop and Context Ledger](./phase-05-iterative-tool-loop-and-context-ledger.md) | Pending |
| 6 | [Event Stream and Session UX](./phase-06-event-stream-and-session-ux.md) | Pending |
| 7 | [MCP Client and Extension Hooks](./phase-07-mcp-client-and-extension-hooks.md) | Pending |
| 8 | [Git Delivery Workflow](./phase-08-git-delivery-workflow.md) | Pending |
| 9 | [Evaluation Hardening and Release](./phase-09-evaluation-hardening-and-release.md) | Pending |

## Dependencies

- No unfinished plan blocks this roadmap; the three existing plans are complete.
- Phases execute in order. Phase 1 establishes schema migration and baseline metrics used by every later phase.
- Phase 4 depends on Phases 2-3. Phases 5-8 depend on the safe execution and policy contracts. Phase 9 validates all prior phases.
- Every phase is a separately shippable checkpoint with focused conventional commits; never stage `.codex/config.toml` or secrets.

## Acceptance Criteria

- A user can point the agent at a Python or Node repository and receive discovered instructions, safe commands, tests, progress events, resumable state, and a grounded final report.
- All process launches remain argv-based with `shell=False`, bounded time/output, D-drive runtime paths, explicit policy decisions, and approval for destructive or remote effects.
- Existing saved tasks migrate deterministically; recovery, read-only mode, approval, checkpoint, and report contracts remain compatible.
- MCP and Git integrations are deny-by-default, observable, and testable without network access; push and force-like operations are never automatic.
- Local golden issue tasks prove analyze/edit/test/recover behavior. Optional external benchmarks run only when their container/cache roots are verified on D.
- Each phase passes focused tests, full unit suite, branch coverage gate, wheel smoke test, and secret scan before its final commit.

## Delivery Rules

- Test first at each commit boundary; prefer 2-4 focused commits per phase.
- No direct feature copying: each adopted idea must map to a measured gap and repository-native interface.
- Keep single-owner Python modules near 200 lines when practical; split `cli.py`, `orchestrator.py`, and `executor.py` by responsibility during the phase that changes them.
- Stop a phase if its safety invariant cannot be expressed as an automated test.
