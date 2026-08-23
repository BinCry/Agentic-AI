# Executable Coding Workflow

## Start

The `run` command connects the persisted state machine, skill router,
repository retrieval, controlled tools, and a selected model provider. OpenAI
Responses remains the default and reads `OPENAI_API_KEY`; OpenRouter reads only
`OPENROUTER_API_KEY`. No secret option exists on the CLI.

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

Select OpenRouter Responses independently from the embedding provider:

```powershell
$env:OPENROUTER_API_KEY = '<set through your trusted secret source>'
python -B -m coding_agent --workspace D:\Agentic-AI run `
  --issue 'Apply the requested repository change' `
  --model-provider openrouter
```

Repeat `--model-provider openrouter` when resuming an OpenRouter-backed task;
provider selection is run-scoped and is not persisted with task state.

## Read-only analysis

Every structured model turn includes the complete required JSON schema. When
the issue explicitly requests repository inspection, explanation, or analysis
without changes, start it with controller-owned `--read-only`. The persisted
task then pins `IssueAnalysis.task_type` to `analysis`. That path performs
grounded retrieval and evidence verification, then produces a cited final report
without entering planning, mutation, testing, review, or approval states.

```powershell
python -B -m coding_agent --workspace D:\Agentic-AI run `
  --issue 'Phan tich cau truc du an va khong chinh sua file' `
  --model-provider openrouter `
  --read-only
```

`--read-only` cannot be combined with `--auto-approve` and is valid only when
starting a new `--issue`; the mode is persisted for later resume. A failed
terminal task cannot be resumed, so start a new `--issue` after correcting a
provider or structured-output failure.

When the target workspace does not contain the runtime's reusable skills, pass
the skill catalog explicitly. Absolute skill roots are read-only dependencies;
they do not broaden the target workspace's write boundary:

```powershell
python -B -m coding_agent --workspace D:\Studocu run `
  --issue 'Phan tich toan bo cau truc du an va khong chinh sua file' `
  --skill-root D:\Agentic-AI\.claude\skills `
  --model-provider openrouter `
  --read-only
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

## Safe local verification

Verification discovery maps observed repositories to typed profiles. Python
repositories with `tests/test*.py` expose `python.test`; the compatibility name
`unit` resolves to it. A Node `scripts.test` entry is executable only when it is
exactly reducible to direct `node --test`; npm/yarn/pnpm script shells are not
used. The legacy `fixture` profile remains available for regression workflows.

`process.run` accepts a registered executable plus argv, a contained cwd, a
small environment allowlist, and limits no larger than the tool's 60-second and
64-KB budgets. `python -c`, pytest plugins, package install/exec, shell syntax,
outside-workspace test paths, unknown executables, and credential-like
environment values are rejected before approval or spawn.

Local execution requires explicit `--workspace-trust trusted` and still pauses
for approval in `auto-edit`. Approval is not isolation: trusted repository test
code runs with the current user process authority and may itself perform side
effects. Untrusted repositories remain non-executable until a future isolated
boundary is configured.

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
- `--model-provider`: `openai` or `openrouter`; default `openai`.
- `--embedding-provider`: `deterministic` or `openai`.
- `--read-only`: controller-owned analysis mode for a new task; incompatible with `--auto-approve`.
- `--skill-root`: workspace-relative by default; an explicit absolute path is read-only and may be outside the workspace.
- `--repository` is valid only with a new `--issue` run.
- `--issue` and `--task-id` are mutually exclusive.

Runtime state stays under `<workspace>/.coding-agent`; writable paths remain
inside the workspace. Workspace, runtime, and external read-only dependencies
still reject drive `C:` by default on Windows.
