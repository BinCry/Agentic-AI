---
phase: 5
title: "Iterative Tool Loop and Context Ledger"
status: in-progress
effort: "6-8 days"
dependsOn: [1, 3, 4]
---

# Phase 5: Iterative Tool Loop and Context Ledger

## Overview

Evolve the rigid one-decision-per-stage flow into a bounded iterative tool loop while keeping the durable outer workflow states. Add durable observations, token/usage accounting, and termination budgets so the model can inspect, act, test, and adapt without uncontrolled autonomy.

## Requirements

- The model may choose one typed tool action or a terminal stage result per turn; no hidden parallel actions.
- Enforce maximum turns, model tokens, command time, output bytes, repeated identical actions, and wall-clock budget.
- Persist tool-call idempotency keys and observations before the next model call; resume must not duplicate completed side effects.
- Replace character-only context truncation with budgeted sections and observation references while preserving grounded citations.
- Propagate provider usage/latency into Phase 1 accounting; never expose private reasoning text.

## Architecture

Keep `WorkflowEngine` and terminal statuses as the durable control plane. Extract stage handlers from the oversized orchestrator. `AgentTurnLoop` runs within ANALYZE/PLAN/EDIT/TEST/DEBUG/REVIEW boundaries and consumes an `AgentTurnDecision` union (`tool_call` or `stage_result`). `ObservationStore` keeps bounded summaries plus digests/pointers to full local artifacts. `ContextBudgeter` allocates tokens by priority: safety/instructions, issue/state, cited evidence, recent observations, then history.

## File Inventory

| Action | Path | Responsibility |
|---|---|---|
| Create | `src/coding_agent/models/agent_turn.py` | Typed action/result union and validation |
| Create | `src/coding_agent/storage/observation_store.py` | Atomic bounded observations and idempotency records |
| Create | `src/coding_agent/workflow/turn_loop.py` | Budgeted decide/act/observe loop |
| Create | `src/coding_agent/workflow/stage_handlers.py` | State-specific goals and terminal validation |
| Create | `src/coding_agent/workflow/context_budget.py` | Token estimates, section priorities, citation retention |
| Modify | `src/coding_agent/workflow/context.py` | Observation references and budget projection |
| Modify | `src/coding_agent/workflow/orchestrator.py` | Thin coordinator using handlers/turn loop |
| Modify | `src/coding_agent/llm/structured_output.py` | Preserve validated response usage and latency |
| Modify | `src/coding_agent/llm/provider.py`, provider implementations | Normalize usage without reasoning payloads |
| Modify | `src/coding_agent/models/task_state.py` | Turn counters, ledger, observation cursor, terminal budget reason |
| Modify | `src/coding_agent/tools/executor.py` | Idempotency key and observation persistence hooks |
| Create | `tests/test_turn_loop.py`, `tests/test_context_budget.py`, `tests/test_observation_store.py` | Budget/resume/grounding contracts |
| Modify | `tests/test_orchestrator*.py`, `tests/test_structured_output.py`, provider tests | Compatibility and usage propagation |
| Update | `docs/system-architecture.md`, `docs/reliability-and-recovery.md` | Loop, budgets, and recovery |

## Test Scenario Matrix

| Scenario | Expected result |
|---|---|
| Tool result leads to revised next action | New turn receives bounded observation and can progress |
| Same mutating call replayed after crash | Existing result reused; side effect not repeated |
| Identical failing action repeats | Loop stops at configured repeat threshold with grounded reason |
| Turn/token/time/output budget exhausted | Deterministic FAILED/needs-user terminal result; state remains resumable |
| Evidence exceeds context | Cited chunks and provenance survive; low-priority history compacts first |
| Provider omits usage | Ledger marks unknown, never invents counts |
| Provider returns reasoning details | Not persisted or displayed; only supported numeric usage retained |

## Interface Checklist

- `AgentTurnDecision` enforces exactly one of `tool_call` and `stage_result`
- `AgentTurnLoop.run_stage(goal, completion_schema) -> StageOutcome`
- `ObservationStore.append()/get()/find_by_idempotency_key()`
- `ContextBudgeter.project(sections, budget) -> ProjectedContext`
- `StructuredOutputResult` carries normalized `ModelUsage` and latency
- `CodingWorkflowOrchestrator` delegates; it no longer owns tool-specific edit/test logic

## Implementation Steps

1. Add deterministic loop, duplicate-side-effect, budget, and citation-retention tests.
2. Persist observations/idempotency and wire normalized provider accounting.
3. Implement context budgeting with conservative tokenizer-independent fallback.
4. Extract stage handlers, implement the turn loop, and migrate one stage at a time.
5. Compare old/new golden workflows, then remove unreachable legacy branches.

## Commit Boundaries

1. `test(workflow): define bounded iterative action contracts`
2. `feat(state): persist observations and model usage`
3. `feat(context): add budgeted grounded projection`
4. `refactor(workflow): run stages through iterative tool loop`

## Success Criteria

- [ ] Interrupted mutating calls resume without duplicate side effects.
- [ ] Every loop has deterministic turn/token/time/output/repetition termination.
- [ ] Grounded citations remain valid after compaction.
- [ ] Usage and latency are durable for supported providers and explicitly unknown otherwise.
- [ ] Existing read-only scenario still completes; edit/debug scenarios can adapt across multiple observations.

## Checkpoint

Core contracts, durable observations/idempotency, provider accounting, grounded
context budgeting, and the bounded stage loop are implemented and verified. The
outer orchestrator still uses the legacy stage flow, so Phase 5 remains open.

Resume from the [Phase 5 checkpoint report](./reports/pm-260824-0056-phase-05-checkpoint.md).

## Risks and Rollback

- A flexible loop can lose state-machine guarantees. Keep outer transitions authoritative and gate each stage result with existing schemas.
- Observation storage can grow indefinitely. Enforce per-item/session quotas and explicit retention; never delete cited artifacts during an active task.
