---
title: "OpenRouter Ox Alpha Integration"
date: 2026-08-23
tags: [openrouter, ox-alpha, provider, security]
---

# OpenRouter Ox Alpha Integration

## Context

DeepSeek live verification reached the API but lacked balance. OpenRouter
`stealth/ox-alpha` was selected as the free coding/agentic model.

## What Happened

- Replaced the uncommitted DeepSeek slice with an OpenRouter Responses adapter.
- Reused bounded HTTPS, retry, redirect rejection, response-size, and redaction.
- Added run-scoped `--model-provider openrouter`; OpenAI remains default.
- Verified 136 tests, 82% coverage, and one live 115-token Ox Alpha response.

## Reflection

Using the existing Responses contract avoided a parallel chat client and kept
the change small. Provider choice must be repeated on resume because it is not
persisted. Ox Alpha provider retention is a real repository-confidentiality
constraint even though retained content is not used for training.

## Decisions

- Keep model and embedding provider selection independent.
- Keep secrets environment-only and rotate any credential pasted into chat.
- Keep streaming, Anthropic Messages, and direct model tool calls out of scope.

## Next

- Rotate the exposed test key before continued use.
- Commit and push only when explicitly requested.
