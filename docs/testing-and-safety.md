# Testing and Safety

## Disk policy

Runtime root mặc định là `.coding-agent` bên trong workspace. `WorkspacePaths` từ chối runtime ngoài workspace, path traversal và ổ `C:` theo mặc định trên Windows. Policy chỉ kiểm soát các ghi do runtime mới thực hiện; script legacy phải tiếp tục được chạy với `TEMP`, `TMP`, `HOME`, `USERPROFILE` và cache trỏ vào D.

## Test command

Xem lệnh PowerShell đầy đủ trong README. Điều kiện bắt buộc trước khi chạy:

- `PYTHONPATH=D:\Agentic-AI\src`
- `CODING_AGENT_TEST_TMP` nằm dưới `D:\Agentic-AI\.tmp`
- `PYTHONDONTWRITEBYTECODE=1`
- các biến temp/home/cache đều trỏ vào D

Sau đó chạy:

```powershell
python -B -m unittest discover -s tests -p 'test_*.py' -v
```

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

## Artifact policy

Không commit `node_modules`, coverage output, bytecode, backup hay runtime task/trace. Lockfiles và manifest phải được commit để dependency có thể tái tạo. Dữ liệu runtime trong `.coding-agent` là local-only và có thể chứa nội dung issue/repository, nên không đưa vào Git.
