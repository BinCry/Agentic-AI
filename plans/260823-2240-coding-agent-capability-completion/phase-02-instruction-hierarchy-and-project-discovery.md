---
phase: 2
title: "Instruction Hierarchy and Project Discovery"
status: pending
effort: "3-4 days"
dependsOn: [1]
---

# Phase 2: Instruction Hierarchy and Project Discovery

## Overview

Teach the agent to understand the target repository before planning: discover scoped instruction files, manifests, languages, package managers, and candidate verification commands. Instructions are data supplied to context, never executable configuration.

## Requirements

- Support hierarchical `AGENTS.md` and `CLAUDE.md` discovery from workspace root to the target file directory with deterministic precedence.
- Preserve the explicit external `--skill-root`; do not require target projects to contain `.claude/skills`.
- Detect Python and Node manifests first; expose unknown ecosystems without guessing commands.
- Bound instruction bytes/files, reject workspace escapes/symlink escapes, and record source paths/hashes.
- Workspace instruction files may narrow behavior but cannot weaken built-in safety policy.

## Architecture

`ProjectInspector` produces a serializable `ProjectProfile` containing ecosystems, manifests, candidate commands, and instruction sources. `InstructionResolver` resolves root-to-leaf scopes for a requested path and returns provenance-preserving blocks. `ContextProjector` receives only the relevant bounded blocks. No discovered command executes in this phase.

## File Inventory

| Action | Path | Responsibility |
|---|---|---|
| Create | `src/coding_agent/project/__init__.py` | Public project-inspection contracts |
| Create | `src/coding_agent/project/profile.py` | Typed project/manifests/command candidates |
| Create | `src/coding_agent/project/instructions.py` | Scoped discovery, precedence, hashing, byte limits |
| Create | `src/coding_agent/project/inspector.py` | Python/Node manifest and package-manager detection |
| Modify | `src/coding_agent/models/task_state.py` | Persist immutable project-profile snapshot/reference |
| Modify | `src/coding_agent/workflow/context.py` | Project scoped instructions with provenance |
| Modify | `src/coding_agent/workflow/runtime.py` | Inspect at task creation and controlled refresh |
| Modify | `src/coding_agent/cli.py` | Add `project inspect`; move project commands to a CLI module |
| Create | `tests/fixtures/sample_node_repo/package.json` | Offline Node detection fixture |
| Create | `tests/test_project_instructions.py` | Hierarchy, limits, symlink/path safety |
| Create | `tests/test_project_inspector.py` | Ecosystem and command-candidate detection |
| Modify | `tests/test_workflow_runtime.py`, `tests/test_cli.py` | Snapshot and CLI integration |
| Update | `docs/system-architecture.md`, `docs/project-overview-pdr.md` | Instruction and discovery behavior |

## Test Scenario Matrix

| Scenario | Expected result |
|---|---|
| Root and nested AGENTS files | Root applies broadly; deepest file wins for overlapping local guidance |
| Both AGENTS and CLAUDE at one scope | Documented stable precedence and both provenance entries |
| Oversized/binary instruction | Safely skipped or truncated with diagnostic event |
| Instruction symlink leaves workspace | Rejected before read |
| Python `pyproject.toml` | Python ecosystem and verified candidate commands detected |
| Node lockfile plus `package.json` scripts | Matching package manager and script candidates detected without execution |
| Unknown manifest | Profile records unknown; no invented command |

## Interface Checklist

- `ProjectInspector.inspect() -> ProjectProfile`
- `InstructionResolver.resolve(relative_target: str | None) -> tuple[InstructionBlock, ...]`
- Every `InstructionBlock` has canonical relative path, scope, digest, content, and truncation flag
- `ProjectProfile` serialization is stable and contains no environment secrets
- `project inspect --format json` is usable without a model provider

## Implementation Steps

1. Add instruction precedence, traversal, size-limit, and Python/Node fixture tests.
2. Implement project profile models, workspace-safe resolver, and inspector.
3. Snapshot the profile at task creation and inject relevant instruction blocks into grounded context.
4. Add inspect CLI and documentation; validate existing external-skill behavior.

## Commit Boundaries

1. `test(project): define instruction and manifest discovery contracts`
2. `feat(project): discover scoped instructions and project profile`
3. `feat(context): ground workflow in project instructions`

## Success Criteria

- [ ] Python and Node fixtures produce deterministic project profiles offline.
- [ ] Nested instruction scope and precedence pass positive and adversarial tests.
- [ ] Target repositories without `.claude/skills` run successfully with external `--skill-root`.
- [ ] Context citations identify every included instruction source.
- [ ] No discovered content executes or expands safety permissions.

## Risks and Rollback

- Repository instructions are untrusted prompt input. Clearly delimit them, retain provenance, cap size, and keep policy enforcement outside the model.
- Revert project-profile injection independently; migrated task fields remain backward-compatible defaults.
