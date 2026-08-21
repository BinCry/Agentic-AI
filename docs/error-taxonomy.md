# Error Taxonomy and Recovery

Batch 2 uses stable error codes at the model, workflow and controlled-tool
boundaries. A failed tool result is written to both the tool trace and the
task's durable `ErrorRecord` list. Approval requests remain a separate control
flow and are not recorded as failures.

## Required error codes

| Code | Source | Recoverable | Controller action |
|---|---|---:|---|
| `RETRIEVAL_EMPTY` | A grounded query returned no evidence | Yes | Retry the bounded query set; fail with `MAX_RETRIEVAL_RETRIES` after the configured limit |
| `INVALID_MODEL_OUTPUT` | Structured JSON remained invalid after repair attempts | No | Mark the task `FAILED` and retain the failed decision type/attempt count |
| `PATCH_CONFLICT` | Source digest, hunk context or create target changed | Yes | Clear stale evidence and return to retrieval, verification and replanning |
| `TEST_FAILED` | An allowlisted test profile exited unsuccessfully | Yes | Enter `DEBUGGING` with the failed result in bounded context |
| `TEST_TIMEOUT` | An allowlisted test profile exceeded its timeout | Yes | Enter `DEBUGGING`; the timeout remains explicit in state and trace metadata |
| `ACCESS_DENIED` | A workflow-state or workspace-path access boundary rejected the request | No | Mark autonomous execution `FAILED`; a new authorized request is required |

`APPROVAL_REQUIRED` is not an error. Mutation and test requests use it to enter
`WAITING_APPROVAL`, preserving the exact request identity and argument hash.
Generic contract codes such as `TOOL_REQUEST_INVALID`, `TOOL_IO_ERROR` and
`TOOL_GROUNDING_REQUIRED` remain available for failures outside the six
required categories.

## Persistence and observability

- `ErrorCode` is the shared source of stable string values.
- `WorkflowEngine.record_error` derives the recoverable flag from the taxonomy.
- `ToolExecutor` records typed failures after policy or dispatch evaluation.
- `ToolTraceRecord.result_metadata.error_code` exposes the same code without
  storing raw tool arguments.
- Terminal failure preserves the typed cause instead of replacing it with a
  generic exception-only message.

## Verification

Tests cover empty retrieval, invalid model output, patch conflict, failed and
timed-out tests, access denial, bounded retrieval exhaustion and conflict
routing back through grounded retrieval.
