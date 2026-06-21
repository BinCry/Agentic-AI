---
name: "source-command-ckm-play"
description: "Marketing playbook orchestrator — expert strategy, AI execution, goal tracking"
---

# source-command-ckm-play

Use this skill when the user asks to run the migrated source command `ckm-play`.

## Command Template

Marketing playbook orchestrator with expert-strategized workflows, dependency-graph routing, quality gates, and goal tracking.

<args>$ARGUMENTS</args>

## Actions
- `create <name> [--template <id>]` - Create new playbook from expert template
- `next [name]` - Show and execute next ready step
- `status [name]` - Progress dashboard with blockers
- `list` - All active playbooks
- `blocked [name]` - What's stuck and why
- `learn [name]` - Capture reusable patterns
- `reset <name> [step]` - Reset step or whole playbook
- `gate <name> <step> approve|reject` - Manual quality gate
- `templates [--browse]` - List available templates
- `goals [set|pull] [args]` - Goal tracker dashboard

## Workflow

1. **Parse Arguments** — extract action + args from `$ARGUMENTS`
2. **Route to Action** — activate `ckm:play` skill with `$ARGUMENTS`

## Skill Used
- `ckm:play` — Marketing playbook orchestrator
