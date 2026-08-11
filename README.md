# Claude Kit - Bản quyền bảo lưu

![Python](https://img.shields.io/badge/Python-3.8+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Node.js](https://img.shields.io/badge/Node.js-339933?style=for-the-badge&logo=nodedotjs&logoColor=white)
![TypeScript](https://img.shields.io/badge/TypeScript-007ACC?style=for-the-badge&logo=typescript&logoColor=white)

Claude Kit là bộ workspace kit để dùng với AI coding tools, tập trung vào:

- `/.claude`: rules, hooks, agents, scripts, statusline, skills cho Claude Code
- `/.codex`: skills cho Codex
- `/plans/templates`: template plan để tổ chức công việc
- `CLAUDE.md`: instruction gốc cho agent trong repo này

Repo này phù hợp nếu bạn muốn tải về để:

- dùng nguyên repo như một bộ mẫu tham khảo
- copy `/.claude` và `/.codex` sang project khác
- chia sẻ chung cho team để mọi người có cùng workflow

## Tải Repo

### Cách 1: Dùng git

```bash
git clone https://github.com/BinCry/Claude_Kit.git
cd Claude_Kit
```

### Cách 2: Download ZIP

1. Mở `https://github.com/BinCry/Claude_Kit`
2. Bấm `Code`
3. Chọn `Download ZIP`
4. Giải nén và mở thư mục repo

Lưu ý: repo này khá lớn vì đang giữ nguyên nhiều assets và dependency đã được đóng gói sẵn trong một số skill.

## Yêu Cầu

Nên có sẵn:

- `Node.js 18+`
- `Python 3`
- `Git`
- `bash` trên Windows

Trên Windows, nên có một trong các package manager sau:

- `winget`
- `scoop`
- `choco`

## Cài Nhanh

Nếu bạn chỉ muốn đọc tài liệu hoặc tham khảo skill thì không cần cài gì thêm.

Nếu muốn dùng đầy đủ script và skill:

### Windows

Mở PowerShell:

```powershell
cd .claude\skills
Set-ExecutionPolicy Bypass -Scope Process -Force
.\install.ps1 -PreferPackageManager winget
```

Nếu cần quyền admin cho một số package hệ thống:

```powershell
.\install.ps1 -WithAdmin -PreferPackageManager choco
```

### Linux / macOS

```bash
cd .claude/skills
chmod +x install.sh
./install.sh
```

Script cài đặt sẽ setup các phần chính như:

- `FFmpeg`
- `ImageMagick`
- `pnpm`
- `wrangler`
- `repomix`
- Python virtual environment cho skills

## Cấu Hình

### 1. Biến môi trường

Copy file mẫu:

```bash
cp .claude/.env.example .claude/.env
```

Trên Windows có thể tạo thủ công file `.claude\.env` từ `.claude\.env.example`.

Điền các key bạn cần, ví dụ:

- `GEMINI_API_KEY`
- `STITCH_API_KEY`
- `CLAUDEKIT_API_KEY`
- webhook Telegram / Discord / Slack

### 2. MCP server

Nếu bạn dùng MCP:

```bash
cp .claude/.mcp.json.example .mcp.json
```

Sau đó sửa key và command theo môi trường của bạn.

## Cách Dùng

### Dùng trực tiếp repo này

Bạn có thể mở thẳng thư mục repo bằng công cụ AI coding tương thích và làm việc ngay trên nó để:

- tham khảo skill
- chỉnh rule / hook / script
- tái sử dụng cấu hình cho project khác

### Gắn vào project khác

Thông thường bạn sẽ copy các phần sau sang root project của mình:

- `/.claude`
- `/.codex`
- `/plans/templates`
- `CLAUDE.md`

Khuyến nghị:

- merge thủ công với `.gitignore` hiện có của project, không nên ghi đè mù
- nếu project đã có `CLAUDE.md`, hãy hợp nhất nội dung thay vì thay toàn bộ
- sau khi copy, chạy cài đặt trong `/.claude/skills`

## Thành Phần Chính

### `/.claude`

Chứa phần lõi cho Claude Code:

- `hooks/`: chặn đọc thư mục nặng, chặn file nhạy cảm, notification, status helpers
- `agents/`: các persona như planner, debugger, tester, reviewer
- `skills/`: thư viện skill lớn để mở rộng workflow
- `scripts/`: tiện ích dùng chung như resolve env
- `rules/`: bộ quy tắc làm việc

### `/.codex`

Chứa skill dành cho Codex, dùng cho các workflow tương tự nhưng theo cấu trúc của Codex.

### `/plans/templates`

Chứa mẫu plan để làm:

- bug fix
- feature implementation
- refactor

## Cập Nhật Repo

Nếu bạn clone bằng git:

```bash
git pull origin main
```

Nếu bạn dùng bản copy trong project khác, nên cập nhật có chọn lọc:

- `/.claude/rules`
- `/.claude/hooks`
- `/.claude/scripts`
- skill nào bạn thực sự đang dùng

## Gợi Ý Dùng Thực Tế

- Nếu chỉ cần workflow Claude Code: ưu tiên `/.claude`
- Nếu chỉ cần skill cho Codex: ưu tiên `/.codex`
- Nếu muốn share cho team: giữ repo này như upstream, rồi copy/merge sang từng project

## Repo

- GitHub: `https://github.com/BinCry/Claude_Kit`

## Windows Codex Setup On D Drive

You have 2 supported Windows setups depending on whether Claude-Kit should load in every Codex session or only in selected projects.

### Option A: Global Claude-Kit for Every Project

Use this when you want:

- `CODEX_HOME` on `D:`
- Claude-Kit skills, hooks, agents, and `AGENTS.md` loaded in every project
- one shared Claude-Kit repo on disk instead of copying config into each project

1. Install Claude-Kit globally into `D:\CodexHome`

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install-claude-kit-globally-to-codex-home.ps1 -TargetCodexHome D:\CodexHome
```

If you also want the installer to start the cleanup watcher in the background immediately:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install-claude-kit-globally-to-codex-home.ps1 -TargetCodexHome D:\CodexHome -StartCleanupWatcher
```

If `CODEX_HOME` was already moved earlier and you only want to refresh the global Claude-Kit wiring:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install-claude-kit-globally-to-codex-home.ps1 -TargetCodexHome D:\CodexHome -SkipStateMigration
```

2. Restart VS Code / Codex and verify:

```powershell
codex doctor
```

3. After `codex doctor` confirms `CODEX_HOME` is `D:\CodexHome`, remove the old home on `C:` to free disk space:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\remove-legacy-codex-home-after-migration.ps1 -ExpectedCodexHome D:\CodexHome
```

If you want to start that cleanup watcher in the background right away, run:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start-codex-home-cleanup-watcher.ps1 -ExpectedCodexHome D:\CodexHome
```

This mode preserves built-in Codex `.system` skills, keeps the writable Codex home on `D:\CodexHome`, and points global Claude-Kit skills/hooks/agents back to this repo so updates in `D:\Claude-Kit` are reused everywhere.

### Option B: Project-Local Claude-Kit Only

Use this when you want `CODEX_HOME` on `D:` but only specific trusted projects should load Claude-Kit.

1. Move `CODEX_HOME` to `D:\CodexHome`

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install-codex-home-on-d-drive.ps1 -TargetCodexHome D:\CodexHome
```

2. Attach Claude-Kit only to the project you choose

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\attach-claude-kit-to-project.ps1 -ProjectPath D:\my-project
```

3. Detach it from that project when you no longer want it there

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\detach-claude-kit-from-project.ps1 -ProjectPath D:\my-project
```

4. After you restart Codex / VS Code and confirm `codex doctor` uses `D:\CodexHome`, remove the old home on `C:` to free disk space

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\remove-legacy-codex-home-after-migration.ps1 -ExpectedCodexHome D:\CodexHome
```

This keeps the global Codex home on `D:\CodexHome`, while Claude-Kit is loaded only in projects that you explicitly attach and trust.

