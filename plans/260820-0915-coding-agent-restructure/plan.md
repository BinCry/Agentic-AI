---
title: "Skill-Based Coding Agent with Repository RAG and MCP"
description: "Restructure Claude-Kit into a workspace-safe coding agent and deliver the tested Phase 1 runtime foundation."
status: in-progress
priority: P1
effort: large
branch: main
tags: [coding-agent, skills, workflow, repository-rag, mcp]
created: 2026-08-20
---

# Skill-Based Coding Agent Implementation

## Overview

Restructure the current Claude-Kit distribution into a lean academic Coding Agent runtime while preserving its reusable skill system and supported client adapters.

## Phases

| # | Phase | Status | File |
|---|---|---|---|
| 0 | Repository audit and safe restructure | completed | [phase-00-repository-audit-and-restructure.md](./phase-00-repository-audit-and-restructure.md) |
| 1 | Core task state and workflow | completed | [phase-01-core-task-state-and-workflow.md](./phase-01-core-task-state-and-workflow.md) |
| 2 | Controlled MCP tools | completed | [phase-02-controlled-mcp-tools.md](./phase-02-controlled-mcp-tools.md) |
| 3 | Repository RAG | pending | [phase-03-repository-rag.md](./phase-03-repository-rag.md) |
| 4 | End-to-end coding workflow | pending | [phase-04-end-to-end-coding-workflow.md](./phase-04-end-to-end-coding-workflow.md) |
| 5 | Reliability and recovery | pending | [phase-05-reliability-and-recovery.md](./phase-05-reliability-and-recovery.md) |
| 6 | Evaluation and documentation | pending | [phase-06-evaluation-and-documentation.md](./phase-06-evaluation-and-documentation.md) |

## Dependencies

- Python 3.11+ runtime with writable state and cache paths restricted to the selected workspace on `D:`.
- Existing skill definitions remain readable through a configurable catalog root.
- Supported client mirrors remain intact until a generator and compatibility matrix are validated.

## Success Criteria

- Explicit, testable coding-task state machine and bounded orchestration loop.
- Controlled MCP tool surface without arbitrary destructive shell access.
- Hybrid repository retrieval with exact-source grounding and citations.
- Tests, structured traces, checkpoints, review gates, and machine-readable evaluation.
- No runtime write targets on `C:` and no access outside the configured workspace.
