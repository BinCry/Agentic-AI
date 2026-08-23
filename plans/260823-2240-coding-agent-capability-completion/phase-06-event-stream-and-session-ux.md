---
phase: 6
title: "Event Stream and Session UX"
status: pending
effort: "4-6 days"
dependsOn: [5]
---

# Phase 6: Event Stream and Session UX

## Overview

Make long runs observable and controllable through a durable event stream, NDJSON output, session listing/resume, and cooperative cancellation. Deliver a scriptable CLI first; a rich terminal UI remains deferred.

## Requirements

- Emit correlated, versioned events for task/state, model call, policy, approval, tool, command output summary, budget, checkpoint, and final report.
- Support `--output-format json|ndjson|text`, progress without corrupting machine output, session list/show/resume, and cancel intent.
- Cancellation must terminate the active process tree within a bounded interval and leave a resumable durable state.
- Event payloads are size-bounded and redacted; full prompts, secrets, private reasoning, and unrestricted command output are forbidden.
- Existing one-shot JSON CLI remains backward-compatible.
- Provider transports should support cancellable response streaming where available; partial model text/private reasoning is never persisted as progress.

## Architecture

`EventSink` is a small protocol used by workflow, provider, policy, and tools. `JsonlEventStore` is the durable source; console formatters subscribe during a run. Sequence numbers are per task and assigned atomically. `CancellationToken` is file-backed for cross-process CLI cancellation and polled by the turn loop and process runner.

## File Inventory

| Action | Path | Responsibility |
|---|---|---|
| Create | `src/coding_agent/events/__init__.py` | Public event contracts |
| Create | `src/coding_agent/events/models.py` | Versioned redacted event envelope |
| Create | `src/coding_agent/events/store.py` | Atomic sequence and JSONL persistence |
| Create | `src/coding_agent/events/sinks.py` | Composite/no-op/console sinks |
| Create | `src/coding_agent/session/service.py` | List/show/resume/cancel lifecycle |
| Create | `src/coding_agent/session/__init__.py` | Public session lifecycle contracts |
| Create | `src/coding_agent/session/cancellation.py` | Durable cancellation token |
| Modify | `src/coding_agent/observability/trace.py` | Compatibility projection from events or correlated sink |
| Modify | `src/coding_agent/tools/process.py` | Incremental bounded reads and process-tree cancellation |
| Modify | `src/coding_agent/workflow/turn_loop.py`, `runtime.py` | Emit events and check cancellation |
| Modify | `src/coding_agent/llm/openai_transport.py`, `openai_client.py` | Optional cancellable streaming and usage-finalization |
| Modify | `src/coding_agent/cli.py` | Split commands/formatters; add session and output options |
| Create | `tests/test_event_store.py`, `tests/test_session_service.py`, `tests/test_process_cancellation.py` | Ordering, redaction, cancellation |
| Modify | `tests/test_cli.py`, `tests/test_storage_trace.py`, workflow tests | Output compatibility |
| Update | `docs/end-to-end-workflow.md`, `docs/reliability-and-recovery.md` | Session UX and event schema |

## Test Scenario Matrix

| Scenario | Expected result |
|---|---|
| Long task in NDJSON mode | Valid event object per line followed by terminal event |
| Legacy JSON mode | Single backward-compatible final JSON document |
| Concurrent event append | Unique monotonic task sequence with no partial lines |
| Event contains key/token/prompt-like data | Redacted or rejected before persistence |
| Cancel during command | Child tree terminates within bound; cancellation event/state persisted |
| Cancel during streamed provider response | Transport closes; no partial decision is accepted or persisted |
| Crash after event before state save | Resume reconciles by idempotency/sequence without duplicate side effect |
| Resume completed task | Read-only report; no new model/tool call |

## Interface Checklist

- `EventEnvelope(task_id, sequence, type, timestamp, payload, correlation_id)`
- `EventSink.emit(event)` and `JsonlEventStore.iter_from(sequence)`
- `CancellationToken.request()/is_requested()/clear_after_resume()`
- `SessionService.list()/show()/resume()/cancel()`
- Formatters never mix human progress text into JSON/NDJSON stdout

## Implementation Steps

1. Define event schema/redaction and write ordering/concurrency tests.
2. Implement durable event store and bridge existing traces without losing compatibility.
3. Refactor process execution for bounded incremental output and cooperative cancellation.
4. Add session service, CLI formatters, resume/cancel commands, and documentation.
5. Run crash/cancel/recovery simulations and full quality gates.

## Commit Boundaries

1. `test(events): define ordering redaction and compatibility`
2. `feat(events): add durable correlated event stream`
3. `feat(process): support bounded progress and cancellation`
4. `feat(cli): add session lifecycle and NDJSON output`

## Success Criteria

- [ ] Users see progress within each model/tool boundary during long runs.
- [ ] NDJSON is parseable, ordered, bounded, and secret-free.
- [ ] Cancellation terminates active work and leaves a recoverable task.
- [ ] Session resume never repeats an already committed mutating action.
- [ ] Legacy CLI/MCP behavior and trace consumers remain compatible.

## Risks and Rollback

- Windows process-tree termination differs from POSIX. Use platform-specific tests and retain the existing blocking runner behind a compatibility switch until proven.
- Events can duplicate traces and disk usage. Define one canonical envelope and retention quotas rather than two independent verbose logs.
