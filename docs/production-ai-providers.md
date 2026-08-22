# Production AI Providers

## Overview

The runtime includes one production integration: OpenAI Responses for model
decisions and OpenAI embeddings for semantic repository vectors. Both use the
standard library HTTPS stack, bounded response reads, explicit timeouts,
bounded retry, typed errors, and dependency injection for offline tests.

Deterministic embeddings remain the default until production embedding
configuration is explicitly selected by the runtime caller.

The CLI selects Responses automatically for `run`; use
`--embedding-provider openai` to opt into semantic repository vectors. See
[Executable Coding Workflow](executable-workflow.md).

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

## Failure Behavior

- Missing/invalid configuration raises `OpenAIConfigurationError` before a call.
- Network, timeout, rate-limit, and server failures use bounded retry and then
  raise `OpenAIRequestError` with status, retryability, and attempt count.
- Oversized, malformed, missing-text, misordered, or dimension-invalid results
  raise `OpenAIResponseError`.
- Error messages redact the configured key and cap provider detail length.
- Embedding provider/model/dimension drift invalidates persisted vectors and
  forces a clean incremental rebuild.

## Verification

`tests/test_openai_client.py` and `tests/test_openai_providers.py` use an
injected transport and perform no network calls. They cover configuration
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
