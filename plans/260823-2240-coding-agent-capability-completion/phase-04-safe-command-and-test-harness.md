---
phase: 4
title: "Safe Command and Test Harness"
status: completed
effort: "5-6 days"
dependsOn: [2, 3]
---

# Phase 4: Safe Command and Test Harness

## Overview

Add the missing agent-computer interface: a bounded argv-based command tool and project-native verification profiles. Preserve `shell=False`; arbitrary shell text, pipelines, redirection, command substitution, and implicit network access remain unsupported.

## Requirements

- Accept executable plus argument vector, workspace-relative working directory, bounded timeout/output, and an allowlisted environment overlay.
- Resolve executables deterministically; reject shell metacharacters, path escape, C-drive task roots, secret forwarding, and unapproved network/destructive effects.
- Convert Phase 2 command candidates into explicit test/build/lint profiles only after policy evaluation.
- Support Python and Node offline fixtures; unknown ecosystems stay inspectable but non-executable.
- Return structured exit, timeout, truncation, duration, stdout/stderr digests, and safe excerpts.
- Local execution is available only for an explicitly trusted workspace. Untrusted workspaces require a configured sandbox boundary or receive a deterministic denial.

## Architecture

`CommandService` validates and normalizes a `CommandRequest`, asks the Phase 3 engine for authority, then delegates through an `ExecutionBoundary`. `LocalTrustedBoundary` wraps the existing bounded process primitive and refuses untrusted workspaces. A future container boundary implements the same interface only after its data/temp roots are verified on D. `VerificationRegistry` maps inspected project profiles to typed commands; it replaces hard-coded test branches while retaining `test.run` compatibility. Commands are observations, not raw text appended without limits.

## File Inventory

| Action | Path | Responsibility |
|---|---|---|
| Create | `src/coding_agent/execution/__init__.py` | Public execution-boundary contracts |
| Create | `src/coding_agent/execution/boundary.py` | Trusted-local/sandbox boundary protocol and trust gate |
| Create | `src/coding_agent/tools/command_models.py` | Command request/result and effect metadata |
| Create | `src/coding_agent/tools/command_service.py` | Validation, executable resolution, environment filtering |
| Modify | `src/coding_agent/tools/process.py` | Bounded argv runner with separate output channels |
| Create | `src/coding_agent/verification/registry.py` | Project-native lint/test/build profiles |
| Create | `src/coding_agent/verification/__init__.py` | Public verification registry contracts |
| Create | `src/coding_agent/verification/python_adapter.py` | Python profile detection and commands |
| Create | `src/coding_agent/verification/node_adapter.py` | npm/pnpm/yarn script profiles without install |
| Modify | `src/coding_agent/tools/test_runner.py` | Compatibility facade over registry |
| Modify | `src/coding_agent/tools/contracts.py`, `policy.py`, `executor.py` | Register `process.run` and generalized verification |
| Modify | `src/coding_agent/workflow/orchestrator.py` | Request typed verification profiles; begin stage extraction |
| Create | `tests/test_command_service.py`, `tests/test_verification_registry.py` | Safety and cross-ecosystem contracts |
| Modify | `tests/test_execution_tools.py`, `tests/test_orchestrator.py` | Integration and regression |
| Update | `docs/executable-workflow.md`, `docs/testing-and-safety.md` | Command model and limitations |

## Test Scenario Matrix

| Scenario | Expected result |
|---|---|
| `python -m unittest` in fixture | Structured success with bounded output |
| `npm test -- --runInBand` in Node fixture | Executes only when profile/policy allow it |
| Executable contains `&`, `|`, redirection, or substitution syntax | Rejected before process creation |
| Working directory escapes workspace or resolves to C | Rejected |
| Environment includes API/token/key-like names | Rejected or removed with diagnostic; never traced |
| Command exceeds timeout/output budget | Process terminated; result marked timed-out/truncated |
| Package install/network command | Ask or deny based on explicit effect; never auto-run |
| Untrusted repository requests its test script | Denied before spawn unless isolated boundary configured |
| `python -c`, package-manager exec, or equivalent escape hatch | Immutable deny in trusted-local default rules |
| Unknown profile | Typed not-found result with discovered alternatives |

## Interface Checklist

- `CommandRequest(executable, arguments, cwd, environment, timeout_seconds, maximum_output_bytes)`
- `CommandService.prepare()` is pure and separately policy-testable
- `CommandService.execute()` receives an already-authorized normalized request
- `ExecutionBoundary.execute(request, trust) -> CommandResult`; local boundary requires explicit trust
- `VerificationRegistry.detect(profile)`, `list()`, and `run()`
- Tool result contains no full environment and no unbounded subprocess output

## Implementation Steps

1. Add adversarial command normalization/environment/path tests before registering any tool.
2. Implement typed command models and refactor `run_bounded` without weakening current tests.
3. Add command service and policy integration; default executable prefixes remain minimal.
4. Add Python/Node verification adapters and compatibility facade.
5. Integrate orchestration, docs, full regression, wheel smoke, and secret scan.

## Commit Boundaries

1. `test(process): define safe command boundary`
2. `feat(process): add policy-governed argv execution`
3. `feat(verification): discover Python and Node quality commands`
4. `refactor(workflow): use typed verification profiles`

## Success Criteria

- [x] No supported path invokes a shell parser.
- [x] Approval cannot make an untrusted workspace executable without an isolation boundary.
- [x] Injection/path/environment/timeout/output negative tests all pass.
- [x] Python and Node fixtures can run local verification with structured results.
- [x] Network, install, destructive, and unknown commands never auto-execute.
- [x] Existing `test.run` callers and MCP server remain compatible.

## Risks and Rollback

- Executable allowlisting alone does not make arguments or repository scripts safe. Match command prefix/effect, keep immutable escape-hatch denials, and require explicit trust or isolation.
- Windows child-process cleanup is a known risk; require process-tree termination tests before enabling long-lived commands.
