---
name: "source-command-ckm-play-goals"
description: "Goal tracker — set targets, pull metrics, view progress"
---

# source-command-ckm-play-goals

Use this skill when the user asks to run the migrated source command `ckm-play-goals`.

## Command Template

Track marketing goals — set target values, pull latest metrics from APIs, view progress dashboard.

<args>goals $ARGUMENTS</args>

## Workflow

1. **Parse Arguments** — extract optional subaction (set/pull) and args from `$ARGUMENTS`
2. **Activate Skill** — route to `ckm:play` skill with `goals $ARGUMENTS`

## Skill Used
- `ckm:play` — Marketing playbook orchestrator
