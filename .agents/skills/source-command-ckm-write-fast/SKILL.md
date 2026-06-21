---
name: "source-command-ckm-write-fast"
description: "Write creative & smart copy [FAST]"
---

# source-command-ckm-write-fast

Use this skill when the user asks to run the migrated source command `ckm-write-fast`.

## Command Template

Write creative & smart copy for this user request:
<user_request>$ARGUMENTS</user_request>

## Workflow

- If the user provides screenshots, use `ai-multimodal` skill to analyze and describe the context.
- If the user provides videos, use `ai-multimodal` (`video-analysis`) skill to analyze video content.
- Use `copywriter` agent to write the copy, then report back to main agent.
