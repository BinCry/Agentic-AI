# End-to-End Coding Workflow

Phase 4 adds the bounded coding loop that connects structured model decisions,
repository retrieval, controlled tools, workflow state and final validation.
The orchestrator is provider-neutral; all repository side effects remain behind
the Phase 2 `ToolExecutor` boundary.

## Loop

```text
ANALYZING -> RETRIEVING -> VERIFYING_EVIDENCE -> PLANNING -> EDITING -> TESTING
                                      ^           |
                                      |           v
                                  DEBUGGING <- failed test

TESTING -> REVIEWING -> FINALIZING -> COMPLETED
              |
              v
           EDITING (review findings)
```

`CodingWorkflowOrchestrator` selects one handler from the persisted
`CodingTaskState` at a time. Each model response is validated against a typed
structured-output model. Prompts include only bounded issue, plan, evidence,
recent errors and tool-trace metadata; retrieved source chunks are cited by
path, line range, score and file digest. Retrieval evaluates up to four unique
analysis queries in one bounded retrieval stage, then verifies the selected
evidence against the current workspace before planning.

## Safety and approvals

- Retrieval is performed through the allowlisted `repo.retrieve` tool and its
  grounded evidence is stored in task state. If an early query has no hits,
  later bounded queries remain eligible.
- `VERIFYING_EVIDENCE` is an explicit state. Evidence is sorted by grounding
  score for prompts and stale or missing evidence cannot reach planning.
- `repo.apply_patch` and `test.run` remain approval-gated. The controller owns
  approval and rechecks request identity and argument hash before execution.
- A patch requires current evidence for the target file and a matching raw-byte
  SHA-256 digest. Windows path separators are resolved through the workspace
  boundary before evidence is matched.
- Test failures enter the existing bounded repair state machine; global step,
  repair-iteration and retrieval-retry limits still apply.
- Review must approve before finalization. Completion requires acceptance
  criteria, repository evidence, modified-file evidence and passing tests.
- Finalization records the read-only Git diff (or the applied patch fallback
  for a non-Git fixture), a PR summary and final citations before `COMPLETED`.
  These fields are persisted in the task state and enforced by the model and
  transition engine.

## Deterministic verification

`tests/test_orchestrator.py` builds a temporary fixture repository and uses a
fake provider with fixed structured responses. It exercises retrieval,
grounded patching, approval, the allowlisted `fixture` test profile, review and
completion without an external API or network dependency.

Run the full suite from PowerShell in `D:\HK5\AGENTIC`:

```powershell
$env:PYTHONPATH = 'D:\HK5\AGENTIC\src'
$env:CODING_AGENT_TEST_TMP = 'D:\HK5\AGENTIC\.tmp'
$env:PYTHONDONTWRITEBYTECODE = '1'
python -B -m unittest discover -s tests -p 'test_*.py' -v
```

The current full verification passed 86 tests; two Windows symlink tests were
skipped because the current account does not have symlink privilege.
