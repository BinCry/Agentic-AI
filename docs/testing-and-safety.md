# Testing and Safety

## Disk policy

Runtime root mặc định là `.coding-agent` bên trong workspace. `WorkspacePaths` từ chối runtime ngoài workspace, path traversal và ổ `C:` theo mặc định trên Windows. Policy chỉ kiểm soát các ghi do runtime mới thực hiện; script legacy phải tiếp tục được chạy với `TEMP`, `TMP`, `HOME`, `USERPROFILE` và cache trỏ vào D.

## Test command

Xem lệnh PowerShell đầy đủ trong README. Điều kiện bắt buộc trước khi chạy:

- `PYTHONPATH` trỏ tới `<workspace>\src`
- `CODING_AGENT_TEST_TMP` nằm dưới `<workspace>\.tmp`
- `PYTHONDONTWRITEBYTECODE=1`
- các biến temp/home/cache đều trỏ vào D

Sau đó chạy:

```powershell
python -B -m unittest discover -s tests -p 'test_*.py' -v
```

Phase 2 adds policy, repository, patch, bounded subprocess, Git, executor and
MCP contract coverage. The complete Phase 2 tool contract is documented in
[Controlled MCP Tools](controlled-mcp-tools.md).

Phase 3 adds AST/Markdown chunking, ingestion filters, persistent SQLite
indexing, hybrid retrieval, grounded citations, stale recovery and retrieval
metrics. See [Repository RAG](repository-rag.md).

Phase 4 adds orchestrator E2E coverage for analysis, retrieval, structured plan,
approval, grounded patch, fixture tests, review, finalization and bounded repair
routing. See [End-to-End Coding Workflow](end-to-end-workflow.md).

Batch 2 adds typed failure coverage for empty retrieval, invalid model output,
patch conflicts, failed/timed-out tests and access denial. See
[Error Taxonomy and Recovery](error-taxonomy.md).

Batch 2 finalization also persists a seven-section report, rejects success when
model file claims conflict with controlled state, and exposes verified JSON or
Markdown through the CLI. See
[Structured Final Reporting](structured-final-report.md).

Phase 5 adds valid-JSON context compaction, atomic checkpoint/file rollback,
durable approval ledger and failure-injection coverage. See
[Reliability and Recovery](reliability-and-recovery.md).

Phase 6 adds versioned benchmark fixtures, retrieval/coding-agent metrics,
issue-resolution/test/repair/invalid-tool rates, machine-readable failure
analysis and explicit null handling for missing samples. Repository content is
treated as untrusted evidence, including comments and documentation that may
contain prompt-injection text.
See [Evaluation and Benchmarking](evaluation.md).

## Coverage hành vi

Bộ test Phase 1 bao phủ:

- structured decision validation và completion invariants;
- state serialization với nested records;
- happy path, Definition-of-Done, approval gate, repair test batch và mọi retry/iteration bound;
- skill metadata/digest/routing;
- containment, traversal, forbidden drive, exclusive atomic persistence và symlink collision;
- trace redaction và giới hạn kích thước;
- model-output repair hữu hạn;
- CLI init/show/transition và JSON errors.
- bounded end-to-end orchestration with deterministic fixture provider;
- Windows path-separator normalization and raw-byte patch digest checks.

The latest full verification passed 110 tests; 2 symlink tests were skipped
because the current Windows account lacks symlink privilege.

## Artifact policy

Không commit `node_modules`, coverage output, bytecode, backup hay runtime task/trace. Lockfiles và manifest phải được commit để dependency có thể tái tạo. Dữ liệu runtime trong `.coding-agent` là local-only và có thể chứa nội dung issue/repository, nên không đưa vào Git.
