# Reliability and Recovery

Phase 5 adds crash-safe state protection around the Phase 4 coding loop.
Runtime data remains inside the configured workspace runtime directory.

## Durable boundaries

- `ContextProjector` separates decision-relevant issue, plan progress, debug
  root cause, evidence, bounded recent tests, limits and trace data from
  unbounded task history.
- `ContextCompactor` applies a hard serialized context limit and keeps the
  compacted result valid JSON.
- `CheckpointStore` writes immutable state snapshots atomically before
  approval-gated mutation/test operations.
- Mutation checkpoints include the exact pre-operation bytes of the target file;
  new-file targets are recorded as absent. Recovery restores both state and
  files within workspace containment checks.
- `ApprovalLedger` stores approval decisions independently of the mutable task
  JSON, so a process interruption cannot erase the audit record.

## CLI recovery

From PowerShell in `D:\Agentic-AI`:

```powershell
$env:PYTHONPATH = 'D:\Agentic-AI\src'
python -B -m coding_agent --workspace D:\Agentic-AI checkpoints --task-id demo-01
python -B -m coding_agent --workspace D:\Agentic-AI recover --task-id demo-01
python -B -m coding_agent --workspace D:\Agentic-AI recover `
  --task-id demo-01 `
  --checkpoint-id checkpoint-0004-0001
```

Recovery defaults to the latest checkpoint. The selected snapshot is validated
before it replaces the current task state, and all recorded file snapshots are
restored atomically. Iteration, repair and retrieval counters come from the
checkpoint; recovery never resets limits.

## Saved-state migration

Task state schema version 2 adds typed `run_budget` and `usage_ledger` records.
`JsonTaskStore` and `CheckpointStore` migrate version-1 JSON through the same
pure, ordered migration chain before strict model validation. Unknown future
versions fail without rewriting the source.

Loading a legacy task is read-only. On its first later save, the original bytes
are written once to `.coding-agent/task-backups/<task-id>.v1.json` before the
current state is atomically replaced. An existing backup with different bytes
blocks the save instead of destroying recovery evidence.

## Verification

Failure-injection tests cover checkpoint write failure, state/file rollback,
approval ledger persistence and bounded context compaction. Run the full suite
using [Testing and Safety](testing-and-safety.md).
