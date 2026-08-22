# Phase 3 Executable Workflow Report

Date: 2026-08-22

## Outcome

Production `run` command now starts or resumes the persisted orchestrator.
Default execution pauses mutation/test requests. `--auto-approve` is explicit,
run-scoped opt-in and does not widen policy.

Implementation commit: `5640007035ed02760ab5591b0741d4791ab8d2dc`.

## Delivered

- New issue and existing task paths through one JSON CLI contract.
- Stable exits: completed `0`, configuration `1`, failed `2`, approval `3`.
- OpenAI Responses configured only from environment; no secret CLI argument.
- Deterministic embeddings default; explicit OpenAI semantic selection.
- State saved after every attempted orchestration step and early return.
- Pending requests persist exact arguments plus canonical hash validation.
- External approval resumes plan progress without replaying completed mutation.
- Persisted patch conflict, access denial, and failed test resume correctly.
- Repository evidence serialization preserves exact whitespace/newlines.
- User start, approve, resume, automation, bounds, and exit docs added.

## Verification

- Focused runtime/CLI/orchestrator gate: 39 passed.
- Focused crash/resume regression gate: 8 passed.
- Full suite: 131 passed in 1.920 seconds.
- Combined branch coverage: 82%.
- CLI help smoke: passed; no API-key argument.
- Diff formatting and secret pattern scans: passed.
- Push verification: local and `origin/main` SHA matched.

## Review

Review found two pre-commit production defects: persisted evidence lost source
whitespace, and externally approved failures lacked safe resume semantics. Both
fixed without weakening digest, grounding, approval, or test invariants.

Docs impact: major; new executable user workflow and approval contract.

## Unresolved Questions

None.
