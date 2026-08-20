# Code Standards

## Nguyên tắc

- Ưu tiên module nhỏ, tên đầy đủ và type hints tại public boundary.
- Dùng dataclass cho model nội bộ; dữ liệu từ LLM hoặc disk luôn đi qua `from_dict` và validation.
- Workflow chỉ đổi trạng thái qua `WorkflowEngine`; không sửa counter rải rác ở caller.
- Tất cả writable path phải được tạo hoặc resolve qua `WorkspacePaths`.
- Không log prompt, credential hay payload lớn chưa được giới hạn/redact.
- Provider, retriever và tool adapter phải phụ thuộc interface, không phụ thuộc vendor trong core.

## Lỗi và giới hạn

- Lỗi policy/validation phải có exception cụ thể và thông báo có thể kiểm thử.
- Retry, repair và workflow iteration phải có maximum trong state/config.
- Không nuốt exception tại core. CLI có thể chuyển exception thành JSON error và exit code khác 0.

## Kiểm thử

- Dùng `unittest` trong Phase 1 để giữ runtime không dependency.
- Mỗi bất biến có ít nhất một positive case và một failure case.
- Test temp không dùng `tempfile` mặc định; dùng `CODING_AGENT_TEST_TMP` trên D.
- Test không network, không home directory và không ghi ngoài workspace fixture.
