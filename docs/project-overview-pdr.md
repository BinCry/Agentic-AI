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

## Ngoài phạm vi Phase 1

- MCP server và controlled repository tools.
- Repository RAG/indexing, embeddings và ranking.
- Vòng agent tự động gọi model/tool.
- Benchmark và báo cáo học thuật hoàn chỉnh.

## Yêu cầu phi chức năng

- Python 3.11+, standard-library-first và không cần network để chạy test Phase 1.
- State quan trọng phải validate trước khi ghi.
- Không có workflow loop vô hạn.
- Redact metadata theo key nhạy cảm và các mẫu credential/token có nhãn trước khi ghi trace; caller vẫn không được đưa secret thô không nhãn vào metadata.
- Mọi runtime artifact nằm trong workspace đã chọn trên ổ D.

## Tiêu chí nghiệm thu Phase 1

- Mọi transition sai bị từ chối rõ ràng.
- Counter không vượt giới hạn cấu hình.
- State serialize/deserialize không mất dữ liệu.
- Structured output sai chỉ được sửa với số lần hữu hạn.
- Path traversal và ổ C bị chặn trước khi ghi.
- Unit/CLI integration tests chạy độc lập và qua đầy đủ.
