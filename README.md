# Agentic Coding Agent

![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Node.js](https://img.shields.io/badge/Node.js-18%2B-339933?style=for-the-badge&logo=nodedotjs&logoColor=white)
![TypeScript](https://img.shields.io/badge/TypeScript-Ready-3178C6?style=for-the-badge&logo=typescript&logoColor=white)

Đây là nền tảng coding agent dựa trên skill, được cấu trúc lại từ bộ Claude-Kit hiện có. Runtime mới dùng Python 3.11+, lưu task state ngoài hội thoại, điều phối bằng state machine rõ ràng và tái sử dụng trực tiếp các `SKILL.md` trong repository.

Hiện trạng: Phase 0 đến Phase 4 đã hoàn thành, gồm controlled MCP tools, repository RAG với grounded citations và vòng coding end-to-end có approval, test, repair và review.

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

Approval workflow dùng `request-approval --resume-to EDITING|FINALIZING`, sau đó dùng `approve`. Approval cho tool mutation/test dùng `approve-tool` và luôn kiểm tra lại request hash.

Phase 2 tool surface, policy, approval flow và cách chạy MCP được mô tả trong [Controlled MCP Tools](docs/controlled-mcp-tools.md).

Vòng coding end-to-end, grounding, approval và fixture verification được mô tả
trong [End-to-End Coding Workflow](docs/end-to-end-workflow.md).

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
- [Controlled MCP Tools](docs/controlled-mcp-tools.md)
- [Repository RAG](docs/repository-rag.md)
- [Roadmap](docs/project-roadmap.md)
- [Kế hoạch triển khai chi tiết](plans/260820-0915-coding-agent-restructure/plan.md)

## Giới hạn hiện tại

Phase 1 cung cấp nền móng điều phối và persistence; Phase 2 bổ sung các tool repository/test/Git được allowlist và expose qua JSON-RPC stdio MCP với approval cho mutation/test; Phase 3 bổ sung SQLite hybrid retrieval, citations, grounding và stale recovery; Phase 4 kết nối các thành phần thành bounded coding loop có structured decisions, repair, review và completion invariants. Reliability/recovery nâng cao và benchmark vẫn thuộc Phase 5–6.
