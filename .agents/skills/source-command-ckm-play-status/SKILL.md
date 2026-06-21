---
name: "source-command-ckm-play-status"
description: "Show playbook progress dashboard"
---

# source-command-ckm-play-status

Use this skill when the user asks to run the migrated source command `ckm-play-status`.

## Command Template

Show playbook progress dashboard with stages, steps, goals, and blockers.

<args>status $ARGUMENTS</args>

## Workflow

1. **Parse Arguments** — extract optional playbook name from `$ARGUMENTS`
2. **Activate Skill** — route to `ckm:play` skill with `status $ARGUMENTS`

## Skill Used
- `ckm:play` — Marketing playbook orchestrator
