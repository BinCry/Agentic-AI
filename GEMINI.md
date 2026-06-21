# GEMINI.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Role & Responsibilities

Your role is to analyze user requirements, delegate tasks to appropriate sub-agents, and ensure cohesive delivery of features that meet specifications and architectural standards.

## Workflows

- Primary workflow: `./.agents/rules/primary-workflow.md`
- Development rules: `./.agents/rules/development-rules.md`
- Orchestration protocols: `./.agents/rules/orchestration-protocol.md`
- Documentation management: `./.agents/rules/documentation-management.md`
- And other workflows: `./.agents/rules/*`

**IMPORTANT:** Analyze the skills catalog and activate the skills that are needed for the task during the process.
**IMPORTANT:** DO NOT modify skills in `~/.claude/skills` directory directly. **MUST** modify skills in this current working directory. Unless you are asked to do so.
**IMPORTANT:** You must follow strictly the development rules in `./.agents/rules/development-rules.md` file.
**IMPORTANT:** Before you plan or proceed any implementation, always read the `./README.md` file first to get context.
**IMPORTANT:** Sacrifice grammar for the sake of concision when writing reports.
**IMPORTANT:** In reports, list any unresolved questions at the end, if any.

## Git

**DO NOT** use `chore` and `docs` in commit messages of file changes in `.claude` directory.

## Python Scripts (Skills)

When running Python scripts from `.agents/skills/`, use the venv Python interpreter:
- **Linux/macOS:** `.agents/skills/.venv/bin/python3 scripts/xxx.py`
- **Windows:** `.claude\skills\.venv\Scripts\python.exe scripts\xxx.py`

This ensures packages installed by `install.sh` (google-genai, pypdf, etc.) are available.

**IMPORTANT:** When scripts of skills failed, don't stop, try to fix them directly.

## [IMPORTANT] Consider Modularization
- If a code file exceeds 200 lines of code, consider modularizing it
- Check existing modules before creating new
- Analyze logical separation boundaries (functions, classes, concerns)
- Use kebab-case naming with long descriptive names, it's fine if the file name is long because this ensures file names are self-documenting for LLM tools (Grep, Glob, Search)
- Write descriptive code comments
- After modularization, continue with main task
- When not to modularize: Markdown files, plain text files, bash scripts, configuration files, environment variables files, etc.

## Documentation Management

We keep all important docs in `.` folder and keep updating them, structure like below:

```
./docs
├── project-overview-pdr.md
├── code-standards.md
├── codebase-summary.md
├── design-guidelines.md
├── deployment-guide.md
├── system-architecture.md
└── project-roadmap.md
```

**IMPORTANT:** *MUST READ* and *MUST COMPLY* all *INSTRUCTIONS* in project `./GEMINI.md`, especially *WORKFLOWS* section is *CRITICALLY IMPORTANT*, this rule is *MANDATORY. NON-NEGOTIABLE. NO EXCEPTIONS. MUST REMEMBER AT ALL TIMES!!!*

---

---

---

---

---

## Rule: development-rules

# Development Rules

Use this file when editing code, tests, scripts, or configuration.

## Baseline

- Follow project docs in `docs/` and existing local patterns.
- Prefer YAGNI, KISS, and DRY in that order.
- Implement real behavior. Do not add fake data, mocks, or temporary shortcuts just to satisfy a check.
- Keep changes scoped to the request and the affected contracts.
- Use descriptive kebab-case file names for new files when the repo has no stronger convention.
- Split code only when it reduces real complexity or matches existing module boundaries.

## Quality Gates

- Run the narrowest useful test first, then broaden when shared behavior or public contracts changed.
- Do not hide failing tests, lint, type, build, or syntax errors.
- Preserve public contracts unless the change intentionally updates them and the user accepted that scope.
- Keep commits focused and use conventional commit format without AI references.
- Never commit secrets, dotenv files, tokens, private keys, database credentials, or personal data.

## Tooling

- Use `gh` for GitHub operations when needed.
- Use current docs only when the API/tooling may have changed.
- Use relevant skills by reading their descriptions first, then opening only the needed `SKILL.md`.
- Use `` only when a visual explanation will materially help the user understand the change.
---

## Rule: documentation-management

# Project Documentation Management

Use this file when creating plans or changing project documentation.

## When To Update Docs

Update docs only when the change affects user-visible behavior, setup, commands, architecture, security posture, public contracts, or future maintainer decisions. Do not add changelog noise for purely internal edits unless the repo already requires it.

Common docs:

- `docs/code-standards.md`
- `docs/system-architecture.md`
- `docs/project-roadmap.md` or `docs/development-roadmap.md`
- `docs/project-changelog.md` when present

## Plan Location

Save plans under `plans/<timestamp>-<descriptive-slug>/`.

Use:

```text
plans/<slug>/
  plan.md
  phase-01-<name>.md
  reports/
```

Keep `plan.md` short: status, phases, dependencies, acceptance criteria, and links to phase files.

Phase files should include only the detail needed to execute safely:

- context links
- requirements
- files to modify/create/delete
- implementation steps
- tests or validation
- risks and rollback notes

Before updating docs, read the existing document. After updating, verify dates, links, and claims match the actual change.
---

## Rule: orchestration-protocol

# Orchestration Protocol

Use this file only when spawning subagents or coordinating parallel work.

## Delegation Context

Every subagent prompt should include:

- task
- files to read
- files it may modify
- acceptance criteria
- constraints
- work context path
- reports path, normally `{work_context}/plans/reports/`

If the shell CWD differs from the primary project, use the primary project paths.

## Context Isolation

- Do not pass full conversation history.
- Summarize only decisions needed for the subtask.
- Give exact file paths instead of "look around the repo" unless scouting is the task.
- Keep coordination, merge decisions, and user approvals in the controller session.

## Parallel Work

Use parallel subagents only when file ownership is clear and integration points are known. Avoid parallel edits to the same file, generated artifact, database migration sequence, or shared config.

## Status Protocol

Ask subagents to end with:

```text
Status: DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT
Summary: one or two sentences
Concerns/Blockers: optional
```

Handle `BLOCKED` and `NEEDS_CONTEXT` by changing context, scope, or approach. Do not retry the same failing prompt repeatedly.

For multi-session team work, use `` and its skill-local rules.
---

## Rule: primary-workflow

# Primary Workflow

Use this file when a task needs an implementation workflow beyond a direct answer.

## 1. Understand

- Read the request, relevant docs, and nearby code before planning.
- Clarify only decisions that cannot be discovered from the repo.
- For broad or risky work, create or update a plan in `plans/`.
- For ambiguous workflow sequence, load `.agents/skills/cook/references/workflow-routing.md`.

## 2. Implement

- Change existing files when that matches the design; create new files only for real boundaries.
- Keep behavior compatible unless the accepted scope says otherwise.
- Prefer local helpers, conventions, and test utilities over new abstractions.
- For bugs, prove the cause before changing behavior.

## 3. Verify

- Run focused tests for touched behavior.
- Broaden to lint, typecheck, build, or integration tests when shared contracts changed.
- Fix regressions instead of weakening tests.

## 4. Review and Explain

- Use a reviewer or review skill for high-risk, cross-module, or public-contract changes.
- Update docs only when user-facing behavior, workflows, commands, or architecture changed.
- Explain the result plainly; use `` only for complex workflows or architecture. For mode selection, load `.agents/skills/preview/references/visual-explanation-routing.md`.
---

## Rule: review-audit-self-decision

# Review, Audit, and Decision Rules

Use this file when reviewing code, applying audit feedback, or cutting scope.

## Verified Decisions

Once a decision is verified by source, tests, or an empirical check, do not reverse it because an audit raises an abstract concern. Reverse only when the audit adds new evidence or the context changed.

When rejecting an audit concern, state the verification source briefly.

## User Decisions

Do not silently undo explicit user decisions. This includes thresholds, selected libraries, feature scope, schema shape, pricing, timelines, compliance choices, and UX trade-offs.

If an audit suggests reversing a user decision, present:

- the original decision
- the audit concern
- the trade-off
- the concrete options

Then wait for the user.

## Threat Model

Before applying a security or robustness finding, identify what the code actually stores, protects, or exposes. Fix real failure modes. Document non-issues briefly. Ask when the risk is plausible but depends on product intent.

## Scout First

For questions answerable by reading the repo, scout before asking. Ask only when the repo has conflicting evidence, missing context, business judgment, or high reversibility risk.

## Stable Code Artifacts

Do not put plan IDs, phase numbers, audit labels, or finding codes in code comments, migration names, test names, or commit messages. Explain the invariant or behavior directly.

