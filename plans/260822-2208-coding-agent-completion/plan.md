---
title: "Coding Agent Production Completion"
description: "Close verified runtime, provider, CLI, retrieval-performance, and quality-gate gaps without replacing the existing architecture."
status: completed
priority: P1
effort: 4 phases
branch: main
tags: [coding-agent, production, rag, cli, quality]
blockedBy: []
blocks: []
created: 2026-08-22
---

# Coding Agent Production Completion

## Overview

Extend the completed core into a reproducible Coding Agent: passing baseline,
bounded repository indexing, one production AI integration, executable CLI
orchestration, and enforced acceptance gates. Reuse all current workflow, MCP,
RAG, persistence, recovery, evaluation, and reporting components.

## Evidence Baseline

- 110 tests discovered: 108 pass, 2 error from a removed hard-coded workspace.
- Coverage tool reports 82% combined coverage with branch measurement enabled.
- Full-repository evaluation exceeded 120 seconds and produced a 253 MB index.
- No production LLM or semantic embedding implementation exists.
- CLI exposes state/MCP/evaluation commands but not the orchestrator run loop.
- No GitHub Actions workflow exists; configured coverage gate is zero.
- No grading-label coupling was found in active source, tests, plans, or docs.

## Phases

| Phase | Name | Status |
|---|---|---|
| 1 | [Restore Baseline and Bound Retrieval](./phase-01-restore-baseline-and-bound-retrieval.md) | completed |
| 2 | [Add Production AI Providers](./phase-02-add-production-ai-providers.md) | completed |
| 3 | [Expose Executable Coding Workflow](./phase-03-expose-executable-coding-workflow.md) | completed |
| 4 | [Enforce Reproducible Acceptance](./phase-04-enforce-reproducible-acceptance.md) | completed |

## Dependencies

- Existing plan `260820-0915-coding-agent-restructure` supplies completed core components.
- Python 3.11+; runtime/temp/cache paths remain under the D: workspace.
- Live OpenAI verification is conditional on an available `OPENAI_API_KEY`.

## Acceptance Criteria

- Full test suite and coverage gate pass with no hidden failures.
- Retrieval benchmark completes reproducibly with grounded citations.
- Real Responses API and embeddings adapters have bounded, typed failure behavior.
- CLI can start/resume the existing orchestrator without bypassing approvals.
- Packaging, CLI, MCP/security, recovery, evaluation, and end-to-end smokes pass.
- Local and remote branch SHAs match after every focused phase commit.
