# Codebase Summary

## Runtime mới

- `src/coding_agent/models`: state, decision output, prompt-facing JSON schemas,
  read-only analysis completion, và embedded records.
- `src/coding_agent/workflow`: trạng thái hợp lệ và bounded transition engine.
- `src/coding_agent/workflow/orchestrator.py`: autonomous bounded workflow,
  skill routing and finalization DoD.
- `src/coding_agent/workflow/runtime.py`: production provider/executor assembly,
  persisted start/resume and explicit auto-approval boundary.
- `src/coding_agent/skills`: đọc metadata/content digest từ skill hiện hữu và route theo state.
- `src/coding_agent/llm`: provider protocol, strict structured-output boundary,
  bounded OpenAI HTTPS client, OpenAI Responses, and OpenRouter Responses adapters.
- `src/coding_agent/tools`: allowlisted repository, test and read-only Git/MCP
  tools with approval and trace boundaries.
- `src/coding_agent/rag`: persistent repository index, grounded retrieval and
  stale-evidence recovery.
- `src/coding_agent/storage`: workspace containment và atomic JSON task store.
- `src/coding_agent/evaluation`: versioned retrieval benchmark and honest
  coding-agent metrics.
- `src/coding_agent/observability`: append-only trace, output-size cap và redaction.
- `src/coding_agent/cli.py`: task operations, executable `run`, approvals, MCP,
  reporting and evaluation.

## Tài sản tương thích được giữ

Repository vẫn chứa các adapter/root cho Claude, Codex, Cursor, Gemini, OpenCode và agent clients khác. `guide/SKILLS.yaml` cùng các `SKILL.md` tiếp tục là nguồn skill hiện hữu; orchestrator chọn skill theo workflow state từ skill root cấu hình được, mặc định `.claude/skills`.

## Artifact đã loại khỏi worktree

Các dependency installs (`node_modules`), coverage report, Python bytecode,
install state, runtime task/trace và backup là artifact sinh tự động, không
được commit. Manifest và lockfile được giữ để tái tạo dependency khi cần.

## Test layout

`tests/` kiểm tra model validation, complete decision schemas, read-only analysis,
task-state round trip, workflow bounds,
provider retry/redaction, skill routing, storage/path policy, trace redaction,
approval/crash resume, executable CLI và installed workflow contracts.
