# Executable Coding Workflow

## Start

The `run` command connects the persisted state machine, skill router,
repository retrieval, controlled tools, and OpenAI Responses provider. The API
key is read only from `OPENAI_API_KEY`; no secret option exists on the CLI.

From PowerShell in `D:\Agentic-AI`, with the credential already provided by a
trusted process environment or secret manager:

```powershell
$env:PYTHONPATH = 'D:\Agentic-AI\src'
python -B -m coding_agent --workspace D:\Agentic-AI run `
  --issue 'Apply the requested repository change'
```

The command creates a generated task ID, persists every attempted step, and
prints one JSON outcome. Deterministic repository embeddings remain the
default. Select production semantic embeddings explicitly:

```powershell
python -B -m coding_agent --workspace D:\Agentic-AI run `
  --issue 'Apply the requested repository change' `
  --embedding-provider openai
```

## Approval and Resume

Mutation and test tools pause by default. A paused run returns exit code `3`,
status `WAITING_APPROVAL`, and the exact pending request plus its arguments
hash. Approve that persisted request, then resume the same task:

```powershell
python -B -m coding_agent --workspace D:\Agentic-AI approve-tool `
  --task-id <task-id> `
  --request-id <request-id>

python -B -m coding_agent --workspace D:\Agentic-AI run `
  --task-id <task-id>
```

`approve-tool` rehashes the persisted arguments and rejects any mismatch. Old
task states that predate persisted arguments must supply the original exact
object through `--arguments-json`.

Automation is deliberate opt-in. This invocation approves policy-gated
mutations and test profiles, including a currently persisted pending request,
during only that run:

```powershell
python -B -m coding_agent --workspace D:\Agentic-AI run `
  --task-id <task-id> `
  --auto-approve
```

`--auto-approve` does not broaden the tool allowlist, path boundary, grounding
requirements, test profiles, retry limits, or completion invariants.

## Exit Contract

| Exit | Meaning | Output |
|---:|---|---|
| `0` | completed | JSON outcome on stdout |
| `1` | invalid command/configuration | JSON error on stderr |
| `2` | workflow failed | JSON outcome on stdout |
| `3` | approval required | JSON outcome on stdout |

The outcome contains `task_id`, `status`, step count, reason,
`requires_approval`, and the pending request when applicable. Provider failures
are redacted, mapped to failed task state after task creation, and persisted
before exit.

## Bounds

- `--maximum-steps`: 1 through 200; default 40.
- `--structured-retries`: 0 through 8; default 2.
- `--embedding-provider`: `deterministic` or `openai`.
- `--repository` is valid only with a new `--issue` run.
- `--issue` and `--task-id` are mutually exclusive.

Runtime state stays under `<workspace>/.coding-agent`; writable paths remain
inside the workspace and drive `C:` remains forbidden by default on Windows.
