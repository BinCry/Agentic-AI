# Project Overview and PDR

## Mục tiêu

Xây dựng một coding agent có thể phân tích issue, tìm bằng chứng trong repository, lập kế hoạch, chỉnh sửa, test, debug và review thông qua một workflow hữu hạn. Agent phải tái sử dụng hệ thống `SKILL.md` hiện có thay vì tạo thêm một định dạng prompt cạnh tranh.

## Phạm vi đã hoàn thành

- Task state có kiểu dữ liệu rõ ràng và lưu ngoài hội thoại.
- State machine với transition tường minh, giới hạn iteration/repair/retrieval.
- Skill catalog và router dựa trên trạng thái.
- Giao diện LLM trung lập nhà cung cấp, JSON validation và bounded repair.
- Atomic JSON persistence, append-only JSONL trace và secret redaction.
- CLI cho tạo task, xem state, transition và xem skill routes.
- Workspace policy từ chối ghi ngoài workspace và từ chối ổ `C:` mặc định.
- MCP server cùng controlled repository/test/Git tools và approval ledger.
- Repository RAG/indexing, deterministic hybrid ranking, citations và grounding.
- Vòng agent tự động bounded từ analyze đến verified final report.
- Checkpoint/rollback, bounded context, benchmark và failure analysis.
- Batch 2 hardening cho evidence verification, staged test/debug, typed recovery
  và final report JSON/Markdown.

## Yêu cầu phi chức năng

- Python 3.11+, standard-library-first và không cần network để chạy test Phase 1.
- State quan trọng phải validate trước khi ghi.
- Không có workflow loop vô hạn.
- Redact metadata theo key nhạy cảm và các mẫu credential/token có nhãn trước khi ghi trace; caller vẫn không được đưa secret thô không nhãn vào metadata.
- Mọi runtime artifact nằm trong workspace đã chọn trên ổ D.

## Tiêu chí nghiệm thu hiện tại

- Mọi transition sai bị từ chối rõ ràng.
- Counter không vượt giới hạn cấu hình.
- State serialize/deserialize không mất dữ liệu.
- Structured output sai chỉ được sửa với số lần hữu hạn.
- Path traversal và ổ C bị chặn trước khi ghi.
- Unit/CLI integration tests chạy độc lập và qua đầy đủ.
- Planning không bắt đầu trước khi exact source evidence được xác minh.
- Mutation/test chỉ chạy qua tool policy và approval phù hợp.
- `COMPLETED` yêu cầu passing current tests, review không có finding blocking,
  final diff/citations và structured final report.

Nghiệm thu Batch 2 được ghi tại
[Batch 2 Acceptance Report](batch-2-acceptance.md).
