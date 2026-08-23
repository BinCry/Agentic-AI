---
title: "OpenRouter Responses Provider"
description: "Add a bounded OpenRouter Responses integration for Ox Alpha without replacing existing OpenAI defaults."
status: completed
priority: P1
effort: 1 phase
branch: main
tags: [openrouter, ox-alpha, llm, cli, provider]
created: 2026-08-23
---

# OpenRouter Responses Provider

## Requirements

- Add an OpenRouter provider implementing the existing `LLMProvider` contract
  through the documented OpenAI-compatible Responses endpoint.
- Read credentials only from `OPENROUTER_API_KEY`; never accept or persist keys.
- Add `--model-provider openai|openrouter`; preserve `openai` as the default.
- Default to `stealth/ox-alpha` with bounded output and configurable reasoning.
- Keep deterministic/OpenAI embedding selection independent.

## Files

- Create `src/coding_agent/llm/openrouter_provider.py`.
- Modify `src/coding_agent/llm/__init__.py`.
- Modify `src/coding_agent/workflow/runtime.py` and `src/coding_agent/cli.py`.
- Create focused provider tests and extend runtime/CLI tests.
- Update `README.md`, `docs/production-ai-providers.md`, and
  `docs/executable-workflow.md`.

## Implementation

1. Reuse the dependency-free bounded HTTPS client and Responses mapping.
2. Map OpenRouter-specific environment names, endpoint, model, and reasoning.
3. Add provider selection at the runtime boundary and CLI flag.
4. Replace the superseded uncommitted DeepSeek slice.
5. Run focused tests, full coverage, secret scan, and a minimal live call.

## Acceptance

- Existing OpenAI behavior and defaults remain compatible.
- Missing OpenRouter configuration fails before task creation.
- Request endpoint/model/reasoning and response mapping are verified offline.
- Live Ox Alpha response succeeds without printing or storing the credential.
- Working tree contains no credential material and only intentional changes.

## Out of Scope

- Streaming, Chat Completions, Anthropic Messages, OpenRouter-managed tool calls,
  provider fallback, and OpenRouter embeddings.

## Unresolved Questions

None.

## Completion Evidence

- Focused provider/runtime tests: 8 passed.
- Full suite: 136 passed; combined branch coverage: 82%.
- Live `stealth/ox-alpha` Responses call: completed, 115 total tokens.
- CLI help exposes `--model-provider {openai,openrouter}`.
- Diff formatting and changed-source credential scans: passed.
- Completion report: `reports/pm-260823-1841-openrouter-provider.md`.
