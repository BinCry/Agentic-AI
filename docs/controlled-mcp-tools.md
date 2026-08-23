# Controlled MCP Tools

Phase 2 exposes a small, typed repository-tool surface over JSON-RPC stdio. The
MCP layer is an adapter; workspace policy, approval, task state and persistence
remain owned by the controller.

## Exposed tools

| Tool | Purpose | Approval | Allowed states |
|---|---|---:|---|
| `repo.list_files` | List bounded workspace-relative files | No | Same read states |
| `repo.read_file` | Read one bounded UTF-8 file | No | Analysis, retrieval, planning, editing, testing, debugging, review |
| `repo.search_text` | Exact or explicitly requested regex line search | No | Same read states |
| `repo.find_symbols` | Python AST class/function listing | No | Same read states |
| `repo.retrieve` | Grounded hybrid retrieval with line citations | No | Same read states |
| `repo.create_file` | Create a new file without overwrite | Ask; auto-edit may allow | `EDITING`, `DEBUGGING` |
| `repo.apply_patch` | Apply a single-file unified patch | Ask; auto-edit may allow | `EDITING`, `DEBUGGING` |
| `test.detect_framework` | Detect bounded Python/Node test profiles | No | Same read states |
| `test.run` | Run a discovered `unit`, `fixture`, `python.test`, or `node.test` profile | Ask; never auto-edit | `TESTING`, `DEBUGGING` |
| `process.run` | Run registered verification argv with structured output | Ask; never auto-edit | `TESTING`, `DEBUGGING` |
| `git.status` | Read-only short status | No | Read states |
| `git.diff` | Read-only diff, optionally scoped to paths | No | Read states |
| `git.changed_files` | List files changed from `HEAD` | No | Read states |

There is no arbitrary shell tool. Package install/exec, generic network tools,
credential access and destructive commands remain outside the surface.

## Layered policy and trust

Policy decisions are exactly `allow`, `deny`, or `ask`. Built-in remote-write,
destructive, read-only, path and drive invariants cannot be widened. An explicit
trusted TOML can add typed equality/prefix/effect rules. `--workspace-policy`
is workspace-contained and accepts deny rules only. No expression or code is
evaluated from TOML.

- `read-only`: deny every non-read effect.
- `ask`: preserve approval for workspace writes and local processes.
- `auto-edit`: allow bounded workspace create/patch after checkpoint; test
  processes, network and remote effects still ask or deny.
- `--workspace-trust untrusted`: deny local processes because approval is not
  process isolation.

Explain any registered tool without dispatch or `.coding-agent` creation:

```powershell
python -B -m coding_agent --workspace $repo policy check `
  --tool test.run `
  --arguments-json '{"profile":"unit"}' `
  --state TESTING `
  --mode ask `
  --workspace-trust trusted
```

The output includes matched rule ID, layer, reason code, risk metadata, approval
requirement, and redacted arguments.

## Safety invariants

- Every path is resolved through `WorkspacePaths`; traversal, symlink escapes,
  missing read targets and the forbidden `C:` drive are rejected.
- Tool names, workflow states, fields, argument types and test profiles are
  allowlisted. Unknown fields and unknown tools are rejected.
- Subprocesses use fixed argument arrays with `shell=False`, a reduced
  environment, bounded stdout/stderr, hard timeouts and process-tree cleanup.
- Local process execution requires explicit workspace trust. Python is limited
  to contained `unittest` discovery; Node is limited to direct `node --test`.
  Package-manager scripts are inspected but never passed to a shell.
- Process results contain exit/timeout/truncation/duration, SHA-256 digests and
  redacted excerpts. Full environment maps and unbounded output are not returned.
- Patch operations require the caller's SHA-256 digest of the source file.
  A stale digest or mismatched hunk is rejected before writing.
- Mutating and test requests enter `WAITING_APPROVAL`. Approval is bound to the
  task, request ID, tool name and canonical argument hash; changing arguments
  cannot reuse an approval.
- Tool traces store metadata and hashes rather than raw arguments. The existing
  JSONL trace writer applies secret redaction and event-size limits.

## Running the stdio server

```powershell
$repo = 'D:\Agentic-AI'
$env:PYTHONPATH = Join-Path $repo 'src'
python -B -m coding_agent `
  --workspace $repo `
  --runtime-dir .coding-agent `
  mcp-server `
  --task-id <task-id>
```

The task must already exist in the atomic task store. The server responds to
`initialize`, `tools/list`, `tools/call` and the
`notifications/initialized` notification. State is saved after each request.

When a mutation or test returns `APPROVAL_REQUIRED`, an explicit controller or
human approval must invoke:

```powershell
python -B -m coding_agent `
  --workspace $repo `
  approve-tool `
  --task-id <task-id> `
  --request-id <request-id>
```

Current pending requests persist their exact arguments and verify their
canonical hash before execution. Legacy pending states without persisted
arguments must also pass `--arguments-json '<exact-original-arguments-json>'`.
Changing a path, patch, profile, or other field invalidates the approval.

## Verification

Phase 2 is covered by unit, security, executor, MCP contract and CLI tests.
Run the complete suite with:

```powershell
$repo = 'D:\Agentic-AI'
$env:PYTHONPATH = Join-Path $repo 'src'
$env:CODING_AGENT_TEST_TMP = Join-Path $repo '.tmp'
$env:PYTHONDONTWRITEBYTECODE = '1'
python -B -m unittest discover -s (Join-Path $repo 'tests') -p 'test_*.py' -v
```

The autonomous LLM loop is delivered by Phase 4. Durable approval history,
checkpoint recovery, bounded repair and finalization evidence are delivered by
Phase 5 and Phase 6. During finalization the controller records the final diff,
PR summary and citations before allowing `COMPLETED`.
