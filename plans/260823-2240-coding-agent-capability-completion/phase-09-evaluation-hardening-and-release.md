---
phase: 9
title: "Evaluation Hardening and Release"
status: pending
effort: "6-9 days"
dependsOn: [1, 2, 3, 4, 5, 6, 7, 8]
---

# Phase 9: Evaluation Hardening and Release

## Overview

Prove the upgraded agent solves repository tasks safely. Add local issue-to-patch golden suites, security/chaos scenarios, live-provider evaluation with explicit budgets, and release gates. External benchmarks are optional and cannot write to C.

## Requirements

- Golden suites include read-only analysis, Python bugfix, Node bugfix, failed-test debug/retry, approval pause/resume, cancellation/recovery, and denied unsafe command.
- Separate harness correctness (offline deterministic fixtures) from agent quality (live OpenRouter/OpenAI-compatible provider runs).
- Score patch correctness, verification pass, grounded report, policy violations, recovery, turns/tokens/time/cost, and nondeterministic pass rate.
- Run live evaluation only with explicit provider/model/budget and redacted artifacts; never persist API keys or private reasoning.
- External SWE-bench/Terminal-Bench lane requires verified container/cache/temp roots on D, resource caps, and an explicit opt-in.

## Architecture

Extend `EvaluationRunner` with versioned `IssueTaskCase` and isolated fixture workspaces copied under a D runtime root. Offline tests validate lifecycle/scoring using deterministic protocol fixtures; quality runs invoke the real provider and repeat selected tasks. `ReleaseGate` compares results to Phase 1 baseline and blocks regression or safety failures.

## File Inventory

| Action | Path | Responsibility |
|---|---|---|
| Create | `src/coding_agent/evaluation/issue_tasks.py` | Case schema, isolated workspace setup, expected outcomes |
| Create | `src/coding_agent/evaluation/scoring.py` | Correctness/safety/recovery/efficiency metrics |
| Create | `src/coding_agent/evaluation/release_gate.py` | Threshold and regression comparison |
| Modify | `src/coding_agent/evaluation/runner.py` | Retrieval plus issue-task suites and repetition |
| Modify | `src/coding_agent/cli.py` | `evaluate --suite --provider --budget --repeat` and release gate |
| Create | `tests/fixtures/issue_tasks/python_bugfix/` | Small real failing repository task |
| Create | `tests/fixtures/issue_tasks/node_bugfix/` | Small real failing repository task |
| Create | `tests/fixtures/issue_tasks/safety_and_recovery/` | Adversarial/cancel/resume cases |
| Create | `tests/test_issue_evaluation.py`, `tests/test_release_gate.py` | Harness and threshold contracts |
| Modify | `tests/test_evaluation.py`, workflow/provider tests | Regression and live-run separation |
| Create | `scripts/run-release-gates.ps1` | D-rooted local Windows verification orchestration |
| Update/Create | `docs/evaluation.md`, `docs/project-roadmap.md`, `docs/deployment-guide.md` | Metrics, opt-in external lane, release instructions |
| Update | `README.md`, `release-manifest.json` | Only after every release gate passes |

## Test Scenario Matrix

| Scenario | Expected result |
|---|---|
| Python/Node golden bug | Expected patch semantics and project tests pass |
| Read-only task | Grounded report; zero workspace modification |
| Unsafe command prompt injection | Policy denial; no process/network/write side effect |
| Approval interruption and resume | Same task completes without duplicated mutation |
| Cancel mid-command | Bounded termination and successful later resume |
| Live provider returns invalid structure/transient error | Retry/budget behavior scored; no false pass |
| External benchmark root resolves to C/unknown | Refuse before pulling image/data |
| Metric regression beyond threshold | Release gate fails with comparison report |

## Interface Checklist

- `IssueTaskCase` declares fixture, issue, mode, allowed effects, verification, expected semantic assertions, and budget
- `IssueTaskRunner.run(case, provider) -> IssueTaskResult`
- `EvaluationScore` separates harness error, agent failure, policy failure, and environment failure
- `ReleaseGate.evaluate(current, baseline) -> GateReport`
- CLI requires explicit `--live` plus budget for paid/network provider evaluation

## Implementation Steps

1. Define versioned issue-task schema and build small real Python/Node failing repositories.
2. Implement isolated runner/scoring and offline lifecycle tests; do not treat deterministic fixtures as quality scores.
3. Add safety/chaos/recovery suite and release thresholds.
4. Run bounded live-provider repetitions, inspect failures, and fix product defects rather than weakening assertions.
5. Optionally validate a tiny SWE-bench/Terminal-Bench lane only after D-root and resource checks.
6. Update public docs/manifest, perform production review, and create the final focused release commit.

## Commit Boundaries

1. `test(evaluation): add local issue-to-patch golden tasks`
2. `feat(evaluation): score correctness safety recovery and efficiency`
3. `test(reliability): add chaos and policy regression suite`
4. `feat(release): enforce capability and safety gates`
5. `docs(release): publish verified coding-agent workflow`

## Success Criteria

- [ ] Offline harness tests distinguish infrastructure failure from agent quality failure.
- [ ] All local golden tasks meet semantic, verification, grounding, safety, and recovery thresholds.
- [ ] Bounded live-provider runs report repeatability, tokens, time, and cost/unknown cost honestly.
- [ ] No task-owned temp/cache/container path targets C.
- [ ] Full unit suite, branch coverage gate, wheel smoke, secret scan, package install smoke, and production review pass.
- [ ] README/roadmap claims match measured results and deferred features remain explicit.

## Risks and Rollback

- Benchmarks can reward fixture overfitting. Use semantic assertions, multiple small ecosystems, repeated live runs, and keep fixtures representative.
- Docker defaults can consume C. External lanes are opt-in and hard-fail until Docker data root/cache/temp paths are verified under D.
