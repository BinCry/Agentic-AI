# Evaluation and Benchmarking

Phase 6 provides a dependency-free evaluation runner and a versioned benchmark
fixture. It measures retrieval and, when task-state samples are explicitly
provided, coding-agent outcomes.

## Run evaluation

From PowerShell in `D:\Agentic-AI`:

```powershell
$env:PYTHONPATH = 'D:\Agentic-AI\src'
python -B -m coding_agent --workspace D:\Agentic-AI evaluate `
  --benchmark tests/fixtures/benchmarks/retrieval_cases.json `
  --top-k 5
```

The command prints one JSON report. Use `--task-id` once per persisted task to
include completion, issue-resolution, repair, test, tool-failure, invalid-tool
call and state-citation metrics. If no task IDs are provided, those fields
intentionally contain a zero sample count and `null` rates; the runner never
invents observations.

Each benchmark case uses the versioned schema below:

```json
{
  "case_id": "short-unique-id",
  "query": "repository retrieval query",
  "issue": "the issue represented by the case",
  "relevant_paths": ["src/example.py"],
  "expected_files": ["src/example.py"],
  "acceptance_criteria": ["observable completion condition"],
  "expected_tests": ["tests/test_example.py"]
}
```

## Metric definitions

- `recall_at_k`: relevant benchmark paths retrieved in the top-k divided by
  the number of relevant paths.
- `mrr`: reciprocal rank of the first relevant path, or zero when absent.
- `citation_correctness`: grounded evidence citations divided by returned
  hits; evidence must still match the current file digest and line content.
- `latency_ms`: mean, p95 and maximum retrieval latency emitted by the index.
- `completion_rate`: completed task states divided by supplied task states.
- `issue_resolution_rate`: supplied task states that reached `COMPLETED`; a
  task is only eligible for that state after final diff, summary, citations,
  tests and review invariants pass.
- `repair_rate`: supplied tasks that entered at least one repair iteration.
- `average_repair_attempts`: arithmetic mean of persisted repair iterations;
  `null` when no task states are supplied.
- `test_pass_rate`: task states whose current test batch passed divided by task
  states that supplied a current test batch.
- `regression_pass_rate`: tasks with a passing `unit` test profile divided by
  tasks that supplied unit results.
- `tool_failure_rate`: unsuccessful tool traces divided by all supplied traces.
- `invalid_tool_call_rate`: traces rejected as invalid, rejected by tool
  policy, or blocked because grounded evidence was missing, divided by all
  supplied tool traces.

Every case includes a `failure` object when a relevant path is missing or a
citation is not grounded. This makes benchmark misses auditable instead of
turning them into a fabricated pass.

## Verification result

The checked-in three-case retrieval smoke fixture produced `recall@5=1.0`,
`MRR=0.8333` and `citation_correctness=1.0` during the Phase 6 verification
run. Coding-agent sample count was zero because no persisted task IDs were
passed; its optional rates were therefore `null` by design.

## Failure and risk coverage

- Repository text, comments and documentation are untrusted evidence. Prompt
  injection text is never treated as controller instructions; only typed,
  allowlisted tool requests can execute.
- Workspace containment, forbidden-drive checks, bounded output and redacted
  traces reduce data leakage. Secrets are not copied into prompts or reports
  when they appear in tool metadata.
- Stale RAG evidence is detected by file digest and line-content verification;
  retrieval retries are bounded rather than silently accepting stale context.
- Mutation and test commands are allowlisted, shell-free and approval-gated;
  patch application also requires grounded evidence and an expected digest.
- Checkpoints, atomic writes, approval ledgers and bounded repair/iteration
  counters cover crashes, replay, incorrect patches and infinite repair loops.
