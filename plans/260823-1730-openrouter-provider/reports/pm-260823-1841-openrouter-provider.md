# OpenRouter Provider Completion

Date: 2026-08-23

## Outcome

OpenRouter Responses integration complete. `stealth/ox-alpha` is selectable
through `--model-provider openrouter`; OpenAI remains default.

## Delivered

- Environment-only `OPENROUTER_API_KEY` configuration.
- Default model `stealth/ox-alpha` and configurable reasoning/output bounds.
- Bounded HTTPS, retry, redirect rejection, response limit, and key redaction
  reused from the verified OpenAI-compatible client.
- Runtime/CLI provider selection independent from repository embeddings.
- Provider setup, resume behavior, retention warning, and official references.
- Superseded uncommitted DeepSeek slice removed.

## Verification

| Gate | Result |
|---|---|
| Focused provider/runtime | 8 passed |
| Full suite | 136 passed |
| Combined branch coverage | 82% (80% gate) |
| Live Ox Alpha Responses call | completed; 115 total tokens |
| CLI model selection | `openai`, `openrouter` |
| Compile and diff check | passed |
| Changed-source credential scan | passed |

The live credential existed only in the test process and was removed afterward.
It was not written to repository or runtime files. Because it appeared in chat,
rotate it before continued use.

## Review

- Spec compliance: pass; no missing requirement or unjustified dependency.
- Compatibility: additive CLI/runtime option; OpenAI and embedding defaults unchanged.
- Security: no CLI secret argument, no persistence, bounded/redacted failures.
- Adversarial: no accepted findings; external prompt retention remains a documented
  model-provider property, not a hidden runtime behavior.

Docs impact: major; README, provider guide, executable workflow, architecture,
codebase summary, and roadmap synchronized.

## Unresolved Questions

None.
