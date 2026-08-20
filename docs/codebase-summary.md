# Codebase Summary

## Runtime mới

- `src/coding_agent/models`: state, decision output và embedded records.
- `src/coding_agent/workflow`: trạng thái hợp lệ và bounded transition engine.
- `src/coding_agent/skills`: đọc metadata/content digest từ skill hiện hữu và route theo state.
- `src/coding_agent/llm`: protocol cho model provider và strict structured-output boundary.
- `src/coding_agent/storage`: workspace containment và atomic JSON task store.
- `src/coding_agent/observability`: append-only trace, output-size cap và redaction.
- `src/coding_agent/cli.py`: bề mặt vận hành Phase 1.

## Tài sản tương thích được giữ

Repository vẫn chứa các adapter/root cho Claude, Codex, Cursor, Gemini, OpenCode và agent clients khác. `guide/SKILLS.yaml` cùng các `SKILL.md` tiếp tục là nguồn skill hiện hữu. Phase 1 đọc trực tiếp một skill root cấu hình được, mặc định `.claude/skills`.

## Artifact đã loại khỏi worktree

Các dependency installs (`node_modules`), coverage report, Python bytecode, install state và backup được xem là artifact sinh tự động và đang chờ commit xóa khỏi source control. Manifest và lockfile được giữ để tái tạo dependency trên ổ D khi một skill cụ thể cần chúng.

## Test layout

`tests/` kiểm tra model validation, task-state round trip, workflow bounds, skill routing, storage/path policy, trace redaction, structured output retry và CLI integration.
