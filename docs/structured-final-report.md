# Structured Final Reporting

Batch 2 checkpoint B2.5 adds a persisted, machine-readable final report for
successful coding tasks. A task cannot transition to `COMPLETED` until the
report exists and the existing Definition-of-Done guards have passed.

## Report contract

`FinalReport` contains these required sections:

- `summary`: what was fixed or implemented;
- `root_cause_or_reasoning`: the bug root cause or repository-grounded
  implementation reasoning;
- `changes`: every file modified by controlled tools and its planned purpose;
- `tests`: the current targeted/broad test executions and measured results;
- `review`: approval summary plus the status of any non-blocking finding;
- `evidence`: repository citations supplied at finalization;
- `remaining_limitations`: known limitations and non-blocking findings, or an
  explicit `No known limitations.` entry.

The report also carries `status`, which is `completed` for a successful report.
All sections are persisted under `final_report` in `CodingTaskState`.

## Grounding and completion rules

The model supplies the concise summary, reasoning, citations and known
limitations through `TaskCompletionResult`. The controller builds the report
from persisted workflow evidence instead of accepting unverified success
claims:

- reported modified files must exactly match `state.modified_files` recorded by
  controlled repository tools;
- the current test batch must exist and every execution must pass without a
  timeout;
- high or critical review findings block finalization;
- changes are linked to the matching implementation-plan steps;
- test lines are generated from `TestExecution` records;
- review findings and citations are copied into explicit report sections;
- the final Git diff, acceptance criteria, retrieval evidence, PR summary and
  citations remain mandatory completion invariants.

If model claims conflict with controlled state, finalization records
`INVALID_MODEL_OUTPUT` and fails safely. It never emits a successful report.

## CLI output

Print only the structured JSON report:

```powershell
$env:PYTHONPATH = 'D:\Agentic-AI\src'
python -B -m coding_agent --workspace D:\Agentic-AI report `
  --task-id demo-01
```

Print the same verified report with human-readable headings:

```powershell
python -B -m coding_agent --workspace D:\Agentic-AI report `
  --task-id demo-01 `
  --format markdown
```

The command rejects non-completed tasks and does not expose the raw final diff.
Use `show --task-id <id>` when the complete persisted task state is required.

## Verification

Coverage includes report construction, all seven required sections, Markdown
rendering, persistence round trips, CLI JSON output, non-blocking limitations,
failed current tests, missing completion reports and model/tool modified-file
conflicts.
