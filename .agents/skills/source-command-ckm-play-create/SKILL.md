---
name: "source-command-ckm-play-create"
description: "Create a new marketing playbook from expert template"
---

# source-command-ckm-play-create

Use this skill when the user asks to run the migrated source command `ckm-play-create`.

## Command Template

Create a new marketing playbook from an expert-strategized template.

<args>create $ARGUMENTS</args>

## Workflow

1. **Parse Arguments** — extract playbook name and optional `--template` flag from `$ARGUMENTS`
2. **Activate Skill** — route to `ckm:play` skill with `create $ARGUMENTS`

## Skill Used
- `ckm:play` — Marketing playbook orchestrator
