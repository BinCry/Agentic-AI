# Production AI Providers

## Overview

The runtime includes OpenAI Responses and OpenRouter Responses for model
decisions. OpenAI embeddings provide optional semantic repository vectors.
All production providers use the standard library HTTPS stack, bounded
response reads, explicit timeouts, bounded retry, typed errors, and dependency
injection for offline tests.

The provider-neutral prompt boundary supplies a complete JSON schema for every
workflow decision on the first attempt. Repair retries remain bounded, but are
reserved for genuinely malformed provider output instead of discovering required
fields one validation error at a time.

Deterministic embeddings remain the default until production embedding
configuration is explicitly selected by the runtime caller.

The CLI selects OpenAI Responses by default. Use `--model-provider openrouter`
for OpenRouter and `--embedding-provider openai` to opt into semantic repository
vectors independently. See [Executable Coding Workflow](executable-workflow.md).

## Configuration

Set credentials only through the process environment. Do not pass keys as CLI
arguments or write them into task state, traces, plan files, or Git.

| Variable | Default | Purpose |
|---|---|---|
| `OPENAI_API_KEY` | required for live calls | API authentication |
| `OPENAI_MODEL` | `gpt-5.6` | Responses API model |
| `OPENAI_REASONING_EFFORT` | `medium` | bounded reasoning effort |
| `OPENAI_MAX_OUTPUT_TOKENS` | `8000` | response output limit |
| `OPENAI_TIMEOUT_SECONDS` | `60` | per-request timeout |
| `OPENAI_MAX_RETRIES` | `2` | retry count for transient failures |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` | HTTPS API base |
| `OPENAI_EMBEDDING_MODEL` | `text-embedding-3-small` | embedding model |
| `OPENAI_EMBEDDING_DIMENSION` | `1536` | required vector dimension |
| `OPENAI_EMBEDDING_BATCH_SIZE` | `32` | bounded ordered batch size |
| `OPENROUTER_API_KEY` | required when selected | API authentication |
| `OPENROUTER_MODEL` | `stealth/ox-alpha` | Responses API model |
| `OPENROUTER_REASONING_EFFORT` | `medium` | bounded reasoning effort |
| `OPENROUTER_MAX_OUTPUT_TOKENS` | `8000` | response output limit |
| `OPENROUTER_TIMEOUT_SECONDS` | `60` | per-request timeout |
| `OPENROUTER_MAX_RETRIES` | `2` | retry count for transient failures |
| `OPENROUTER_BASE_URL` | `https://openrouter.ai/api/v1` | HTTPS API base |

OpenRouter model selection is independent from repository embeddings. Ox Alpha
is a third-party stealth preview; its provider retains prompts and completions,
so do not send repository content that its retention terms do not permit.

## Failure Behavior

- Missing/invalid configuration raises `OpenAIConfigurationError` before a call.
- Network, timeout, rate-limit, and server failures use bounded retry and then
  raise `OpenAIRequestError` with status, retryability, and attempt count.
- Oversized, malformed, missing-text, misordered, or dimension-invalid results
  raise `OpenAIResponseError`.
- Error messages redact the configured key and cap provider detail length.
- Embedding provider/model/dimension drift invalidates persisted vectors and
  forces a clean incremental rebuild.
- Missing OpenRouter credentials and invalid OpenRouter settings raise
  `OpenRouterConfigurationError`; request/response failures retain the shared
  bounded and redacted OpenAI-compatible error contract.
- Exhausted structured-output retries persist the final validation detail without
  persisting the raw provider response.

## Verification

`tests/test_openai_client.py`, `tests/test_openai_providers.py`, and
`tests/test_openrouter_provider.py` use an injected transport and perform no
network calls. They cover configuration
rejection, transient status and timeout retry, key redaction, redirect-safe
transport, Responses mapping, malformed/non-standard output, ordered embedding
batches, finite-value and dimension validation, index invalidation, and legacy
provider support.

A live smoke is optional and must run only when a credential is already
available. Absence of a credential is reported as unavailable, never as pass.

## Official References

- [Responses API](https://developers.openai.com/api/reference/resources/responses/methods/create)
- [Model guidance](https://developers.openai.com/api/docs/guides/latest-model)
- [Embeddings API](https://developers.openai.com/api/reference/resources/embeddings/methods/create)
- [text-embedding-3-small](https://developers.openai.com/api/docs/models/text-embedding-3-small)
- [OpenRouter Responses API](https://openrouter.ai/docs/api/api-reference/responses/create-responses)
- [OpenRouter reasoning tokens](https://openrouter.ai/docs/guides/best-practices/reasoning-tokens)
- [Ox Alpha model](https://openrouter.ai/stealth/ox-alpha)
