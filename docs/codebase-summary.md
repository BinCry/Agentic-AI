# Codebase Summary

## Runtime mới

- `src/coding_agent/models`: state, decision output và embedded records.
- `src/coding_agent/workflow`: trạng thái hợp lệ và bounded transition engine.
- `src/coding_agent/workflow/orchestrator.py`: autonomous bounded workflow,
  skill routing and finalization DoD.
- `src/coding_agent/skills`: đọc metadata/content digest từ skill hiện hữu và route theo state.
- `src/coding_agent/llm`: protocol cho model provider và strict structured-output boundary.
- `src/coding_agent/tools`: allowlisted repository, test and read-only Git/MCP
  tools with approval and trace boundaries.
- `src/coding_agent/rag`: persistent repository index, grounded retrieval and
  stale-evidence recovery.
- `src/coding_agent/storage`: workspace containment và atomic JSON task store.
- `src/coding_agent/evaluation`: versioned retrieval benchmark and honest
  coding-agent metrics.
- `src/coding_agent/observability`: append-only trace, output-size cap và redaction.
- `src/coding_agent/cli.py`: bề mặt vận hành Phase 1.

## Tài sản tương thích được giữ

Repository vẫn chứa các adapter/root cho Claude, Codex, Cursor, Gemini, OpenCode và agent clients khác. `guide/SKILLS.yaml` cùng các `SKILL.md` tiếp tục là nguồn skill hiện hữu; orchestrator chọn skill theo workflow state từ skill root cấu hình được, mặc định `.claude/skills`.

## Artifact đã loại khỏi worktree

Các dependency installs (`node_modules`), coverage report, Python bytecode,
install state, runtime task/trace và backup là artifact sinh tự động, không
được commit. Manifest và lockfile được giữ để tái tạo dependency khi cần.

## Test layout

`tests/` kiểm tra model validation, task-state round trip, workflow bounds, skill routing, storage/path policy, trace redaction, structured output retry và CLI integration.
