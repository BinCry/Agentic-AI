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
include completion, repair, regression-test, tool-failure and state citation
metrics. If no task IDs are provided, those fields intentionally contain a
zero sample count and `null` rates; the runner never invents observations.

## Metric definitions

- `recall_at_k`: relevant benchmark paths retrieved in the top-k divided by
  the number of relevant paths.
- `mrr`: reciprocal rank of the first relevant path, or zero when absent.
- `citation_correctness`: grounded evidence citations divided by returned
  hits; evidence must still match the current file digest and line content.
- `latency_ms`: mean, p95 and maximum retrieval latency emitted by the index.
- `completion_rate`: completed task states divided by supplied task states.
- `repair_rate`: supplied tasks that entered at least one repair iteration.
- `regression_pass_rate`: tasks with a passing `unit` test profile divided by
  tasks that supplied unit results.
- `tool_failure_rate`: unsuccessful tool traces divided by all supplied traces.

Every case includes a `failure` object when a relevant path is missing or a
citation is not grounded. This makes benchmark misses auditable instead of
turning them into a fabricated pass.

## Verification result

The checked-in three-case retrieval smoke fixture produced `recall@5=1.0`,
`MRR=0.8333` and `citation_correctness=1.0` during the Phase 6 verification
run. Coding-agent sample count was zero because no persisted task IDs were
passed; its optional rates were therefore `null` by design.
