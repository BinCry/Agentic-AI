---
name: "source-command-ckm-docs-llms"
description: "💡💡💡 Generate llms.txt based on the current codebase"
---

# source-command-ckm-docs-llms

Use this skill when the user asks to run the migrated source command `ckm-docs-llms`.

## Command Template

Read and analyze `docs/` directory as the source of truth for documentation.
Generate `llms.txt` file following this format example: https://docs.polar.sh/llms.txt
Put it in the public directory so it can be accessed by the public.

## Additional requests
<additional_requests>
  $ARGUMENTS
</additional_requests>
