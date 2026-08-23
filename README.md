# Agentic Coding Agent

![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Node.js](https://img.shields.io/badge/Node.js-18%2B-339933?style=for-the-badge&logo=nodedotjs&logoColor=white)
![TypeScript](https://img.shields.io/badge/TypeScript-Ready-3178C6?style=for-the-badge&logo=typescript&logoColor=white)

Đây là nền tảng coding agent dựa trên skill, được cấu trúc lại từ bộ Claude-Kit hiện có. Runtime mới dùng Python 3.11+, lưu task state ngoài hội thoại, điều phối bằng state machine rõ ràng và tái sử dụng trực tiếp các `SKILL.md` trong repository.

Hiện trạng: Phase 0 đến Phase 6 và Batch 2 hardening đã hoàn thành, gồm
controlled MCP tools, repository RAG, evidence verification, staged
test/debug/recovery, verified final reporting, recovery crash-safe và evaluation
benchmark machine-readable. Production completion bổ sung OpenAI Responses,
semantic embeddings tùy chọn, CLI `run`, coverage gate và CI packaging smoke.

## An toàn ổ đĩa

- Runtime mặc định ghi vào `<workspace>/.coding-agent`.
- Mọi đường dẫn ghi phải nằm trong workspace.
- `--skill-root` tuyệt đối có thể nằm ngoài workspace nhưng chỉ được đọc.
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

Khi `OPENAI_API_KEY` đã có trong process environment, chạy workflow thật bằng:

```powershell
python -B -m coding_agent --workspace D:\Agentic-AI run `
  --issue 'Áp dụng thay đổi repository đã yêu cầu'
```

Mutation/test dừng xin duyệt theo mặc định. Xem start/resume, exit code và
`--auto-approve` tại [Executable Coding Workflow](docs/executable-workflow.md).

OpenRouter Responses dùng `--model-provider openrouter` và đọc key từ biến môi
trường `OPENROUTER_API_KEY`; model mặc định là `stealth/ox-alpha`. OpenAI vẫn là
mặc định; lựa chọn model provider độc lập với repository embeddings.

Structured decisions now include their complete JSON schema in the first model
turn. A request that explicitly asks for inspection or explanation without file
changes is classified as read-only analysis: it retrieves and verifies repository
evidence, then completes without planning, mutation, tests, or approval.

```powershell
python -B -m coding_agent --workspace D:\Agentic-AI run `
  --issue 'Phan tich cau truc du an va khong chinh sua file' `
  --model-provider openrouter `
  --read-only
```

Khi phân tích repository khác, giữ skill catalog ở Agentic-AI bằng một đường
dẫn tuyệt đối. Ví dụ workspace đích `D:\Studocu`:

```powershell
python -B -m coding_agent --workspace D:\Studocu run `
  --issue 'Phan tich toan bo cau truc du an va khong chinh sua file' `
  --skill-root D:\Agentic-AI\.claude\skills `
  --model-provider openrouter `
  --read-only
```

Sau khi task đạt `COMPLETED`, xuất báo cáo đã xác minh bằng:

```powershell
python -B -m coding_agent --workspace D:\Agentic-AI report `
  --task-id demo-01 `
  --format markdown
```

Approval workflow dùng `request-approval --resume-to EDITING|FINALIZING`, sau đó dùng `approve`. Approval cho tool mutation/test dùng `approve-tool` và luôn kiểm tra lại request hash.

Phase 2 tool surface, policy, approval flow và cách chạy MCP được mô tả trong [Controlled MCP Tools](docs/controlled-mcp-tools.md).

Vòng coding end-to-end, grounding, approval và fixture verification được mô tả
trong [End-to-End Coding Workflow](docs/end-to-end-workflow.md).

Checkpoint, rollback, context compaction và approval audit được mô tả trong
[Reliability and Recovery](docs/reliability-and-recovery.md).

Mã lỗi ổn định và tuyến phục hồi được mô tả trong
[Error Taxonomy and Recovery](docs/error-taxonomy.md).

Báo cáo cuối có cấu trúc, Definition of Done và lệnh xuất JSON/Markdown được mô
tả trong [Structured Final Reporting](docs/structured-final-report.md).

Benchmark, metric và failure analysis được mô tả trong
[Evaluation and Benchmarking](docs/evaluation.md).

Run the no-API-key capability baseline (tests, coverage, wheel smoke, read-only
workflow, D-drive audit, and retrieval evaluation) with:

```powershell
python -B -m coding_agent --workspace D:\Agentic-AI baseline `
  --output .tmp/quality/baseline.json `
  --require-coverage
```

## Chạy test chỉ trên ổ D

```powershell
$taskTemp = 'D:\Agentic-AI\.tmp\quality'
New-Item -ItemType Directory -Force -Path $taskTemp | Out-Null
$env:TEMP = $taskTemp
$env:TMP = $taskTemp
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

Các root `.claude`, `.codex`, `.agents`, `.agent`, `.cursor`, `.gemini` và
`.opencode` vẫn được giữ để tương thích với các client hiện hữu. `node_modules`,
coverage, bytecode, runtime state, temp data và backup sinh tự động không thuộc
source control; dependency có lockfile thì cài lại từ manifest/lock tương ứng
trên ổ D khi cần.

## Tài liệu

- [Tổng quan và yêu cầu sản phẩm](docs/project-overview-pdr.md)
- [Kiến trúc hệ thống](docs/system-architecture.md)
- [Tóm tắt codebase](docs/codebase-summary.md)
- [Chuẩn code](docs/code-standards.md)
- [Kiểm thử và an toàn](docs/testing-and-safety.md)
- [Controlled MCP Tools](docs/controlled-mcp-tools.md)
- [Repository RAG](docs/repository-rag.md)
- [Production AI Providers](docs/production-ai-providers.md)
- [Executable Coding Workflow](docs/executable-workflow.md)
- [Error Taxonomy and Recovery](docs/error-taxonomy.md)
- [Structured Final Reporting](docs/structured-final-report.md)
- [Batch 2 Acceptance Report](docs/batch-2-acceptance.md)
- [Production Completion Acceptance](plans/260822-2208-coding-agent-completion/reports/final-260822-coding-agent-acceptance.md)
- [Roadmap](docs/project-roadmap.md)
- [Kế hoạch triển khai chi tiết](plans/260820-0915-coding-agent-restructure/plan.md)

## Năng lực đã triển khai

Phase 1 cung cấp nền móng điều phối và persistence; Phase 2 bổ sung các tool
repository/test/Git được allowlist và expose qua JSON-RPC stdio MCP với approval
cho mutation/test; Phase 3 bổ sung SQLite hybrid retrieval, citations, grounding
và stale recovery; Phase 4 kết nối các thành phần thành bounded coding loop có
structured decisions, repair, review và completion invariants; Phase 5 bổ sung
checkpoint/rollback, durable approvals và bounded context; Phase 6 bổ sung
benchmark, metrics và failure analysis có output machine-readable. Batch 2
hardening bổ sung evidence verification tường minh, staged execution/debug,
typed recovery và verified final report.

## Giới hạn còn lại

- Embedding mặc định là deterministic/offline; semantic production chỉ bật khi
  chọn `--embedding-provider openai` và có credential trong environment.
- Live provider smoke không chạy nếu không có credential; offline tests không
  dùng network hay giả lập một lần gọi live thành công.
- Runtime chỉ cho phép tool repository/test/Git đã allowlist, không cung cấp
  shell tùy ý.
- Hai test symlink-hardening trên Windows sẽ skip nếu tài khoản chạy test không
  có quyền tạo symlink.
