---
name: "source-command-ckm-play-next"
description: "Show and execute next ready playbook step"
---

# source-command-ckm-play-next

Use this skill when the user asks to run the migrated source command `ckm-play-next`.

## Command Template

Show smart suggestions and execute the next ready step in a playbook.

<args>next $ARGUMENTS</args>

## Workflow

1. **Parse Arguments** — extract optional playbook name from `$ARGUMENTS`
2. **Activate Skill** — route to `ckm:play` skill with `next $ARGUMENTS`

## Skill Used
- `ckm:play` — Marketing playbook orchestrator
