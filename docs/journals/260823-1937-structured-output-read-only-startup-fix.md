# Structured output and read-only startup fix

Date: 2026-08-23

## Problem

Ox Alpha connected through OpenRouter but failed the first workflow decision:
`IssueAnalysis remained invalid after 3 attempts`. The prompt named the decision
without supplying its required JSON fields. Offline fixtures already returned
perfect payloads, so they did not expose the live contract gap.

The original smoke issue also requested analysis without file changes, while the
coding workflow required plan, mutation, tests, review, and final diff.

The live retry then exposed two Windows portability boundaries: repository
evidence used `\` while model citations used `/`, and targeting `D:\Studocu`
incorrectly searched for reusable skills inside that target repository.

## Decisions

- Put the complete JSON schema for every decision in the first bounded context.
- Persist the final validation detail, never the raw provider response.
- Make read-only authority controller-owned through `--read-only`; do not let the
  model decide whether mutation/test invariants apply.
- Persist read-only mode across resume and reject `--auto-approve` for that task.
- Route verified read-only evidence directly to an analysis-specific completion.
- Reject mutation, test execution, implementation plans, and ungrounded citation
  paths from read-only final reports.
- Serialize new repository evidence with POSIX paths and normalize persisted
  Windows evidence when validating citations.
- Keep all writable tools bounded to the target workspace, while allowing an
  explicit absolute skill root as a forbidden-drive-checked read-only dependency.

## Verification

- Regression baseline: 3 expected failures before implementation.
- Focused workflow tests: passed.
- Full suite: 150 tests passed.
- Branch coverage: 82%, gate 80%.
- Wheel build and installed CLI `--read-only` smoke: passed.
- External target smoke listed 83 skills for workspace `D:\Studocu` from the
  read-only catalog `D:\Agentic-AI\.claude\skills`.
- All temp/cache/build dependencies stayed under `D:\Agentic-AI\.tmp`.

## Unresolved questions

- Re-run one live OpenRouter read-only task against `D:\Studocu`; its environment
  key is intentionally unavailable to the Codex process.
