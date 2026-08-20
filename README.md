# Agentic Coding Agent

![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Node.js](https://img.shields.io/badge/Node.js-18%2B-339933?style=for-the-badge&logo=nodedotjs&logoColor=white)
![TypeScript](https://img.shields.io/badge/TypeScript-Ready-3178C6?style=for-the-badge&logo=typescript&logoColor=white)
![Phase](https://img.shields.io/badge/Phase_1-Complete-2EA44F?style=for-the-badge&logo=githubactions&logoColor=white)
![Tests](https://img.shields.io/badge/Tests-47%2F47_Passing-2EA44F?style=for-the-badge&logo=checkmarx&logoColor=white)

Đây là nền tảng coding agent dựa trên skill, được cấu trúc lại từ bộ Claude-Kit hiện có. Runtime mới dùng Python 3.11+, lưu task state ngoài hội thoại, điều phối bằng state machine rõ ràng và tái sử dụng trực tiếp các `SKILL.md` trong repository.

Hiện trạng: Phase 0 (dọn cấu trúc an toàn) và Phase 1 (task state + workflow foundation) đã hoàn thành. Repository RAG, controlled MCP tools và vòng chạy coding end-to-end thuộc các phase tiếp theo, chưa được quảng cáo là đã triển khai.

## An toàn ổ đĩa

- Runtime mặc định ghi vào `<workspace>/.coding-agent`.
- Mọi đường dẫn ghi phải nằm trong workspace.
- Ổ `C:` bị từ chối theo mặc định trên Windows.
- Test dùng temp/cache dưới `D:\Agentic-AI\.tmp`; không cần cài dependency Python ngoài.

## Chạy nhanh trên Windows

Từ PowerShell trong `D:\Agentic-AI`:

```powershell
$env:PYTHONPATH = 'D:\Agentic-AI\src'
python -B -m coding_agent --workspace D:\Agentic-AI skills
python -B -m coding_agent --workspace D:\Agentic-AI init `
  --task-id demo-01 `
  --issue 'Kiểm tra workflow coding agent' `
  --repository Agentic-AI
python -B -m coding_agent --workspace D:\Agentic-AI show --task-id demo-01
```

Lệnh `init` chọn skill cho trạng thái `ANALYZING`, lưu JSON state nguyên tử và ghi trace JSONL đã che các trường nhạy cảm.

Approval không đi qua lệnh `transition` trực tiếp. Dùng `request-approval --resume-to EDITING|FINALIZING`, sau đó dùng `approve`; resume target được lưu trong task state và validate lại khi đọc từ disk.

## Chạy test chỉ trên ổ D

```powershell
$taskTemp = 'D:\Agentic-AI\.tmp\phase-01'
New-Item -ItemType Directory -Force -Path $taskTemp | Out-Null
$env:TEMP = $taskTemp
$env:TMP = $taskTemp
$env:HOME = $taskTemp
$env:USERPROFILE = $taskTemp
$env:PYTHONPYCACHEPREFIX = Join-Path $taskTemp 'pycache'
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:PYTHONPATH = 'D:\Agentic-AI\src'
$env:CODING_AGENT_TEST_TMP = Join-Path $taskTemp 'tests'
python -B -m unittest discover -s tests -p 'test_*.py' -v
```

## Cấu trúc chính

```text
src/coding_agent/
  models/          task state và structured decision models
  workflow/        trạng thái, transition và giới hạn vòng lặp
  skills/          đọc/routing các SKILL.md hiện hữu
  llm/             provider-neutral interface và JSON validation
  storage/         workspace policy và atomic task store
  observability/   append-only JSONL trace có redaction
tests/             unit và CLI integration tests
docs/              kiến trúc, chuẩn code, kiểm thử và roadmap
plans/             kế hoạch triển khai theo phase
```

Các root `.claude`, `.codex`, `.agents`, `.agent`, `.cursor`, `.gemini` và `.opencode` vẫn được giữ để tương thích với các client hiện hữu. Các cây `node_modules`, coverage, bytecode và backup sinh tự động đã được xóa khỏi worktree và đang chờ commit; dependency có lockfile thì cài lại từ manifest/lock tương ứng trên ổ D khi cần.

## Tài liệu

- [Tổng quan và yêu cầu sản phẩm](docs/project-overview-pdr.md)
- [Kiến trúc hệ thống](docs/system-architecture.md)
- [Tóm tắt codebase](docs/codebase-summary.md)
- [Chuẩn code](docs/code-standards.md)
- [Kiểm thử và an toàn](docs/testing-and-safety.md)
- [Roadmap](docs/project-roadmap.md)
- [Kế hoạch triển khai chi tiết](plans/260820-0915-coding-agent-restructure/plan.md)

## Giới hạn hiện tại

Phase 1 mới cung cấp nền móng điều phối và persistence. CLI chưa gọi LLM thật, chưa chỉnh code tự động, chưa expose tool qua MCP và chưa có repository index/vector search. Các khả năng đó chỉ được thêm khi phase tương ứng có test, policy và approval gate hoàn chỉnh.
