# System Architecture

## Phase 1

```mermaid
flowchart LR
    CLI[CLI] --> WS[Workspace Policy]
    CLI --> Engine[Workflow Engine]
    CLI --> Router[Skill Router]
    Router --> Catalog[Existing SKILL.md Catalog]
    Engine --> State[CodingTaskState]
    State --> Store[Atomic JSON Store]
    CLI --> Trace[Redacted JSONL Trace]
    LLM[LLM Provider Protocol] --> Structured[Structured Output Validator]
    Structured --> State
```

Task state là nguồn sự thật của workflow. Conversation không giữ độc quyền trạng thái. Skill được chọn theo trạng thái và lưu kèm path/content digest để lần chạy sau có thể phát hiện prompt drift.

## State flow

```mermaid
stateDiagram-v2
    [*] --> CREATED
    CREATED --> ANALYZING
    ANALYZING --> RETRIEVING
    RETRIEVING --> PLANNING
    PLANNING --> EDITING
    PLANNING --> WAITING_APPROVAL
    EDITING --> TESTING
    TESTING --> DEBUGGING
    TESTING --> REVIEWING
    DEBUGGING --> RETRIEVING
    DEBUGGING --> EDITING
    REVIEWING --> EDITING
    REVIEWING --> WAITING_APPROVAL
    REVIEWING --> FINALIZING
    WAITING_APPROVAL --> EDITING
    WAITING_APPROVAL --> FINALIZING
    FINALIZING --> COMPLETED
```

Mọi trạng thái đang chạy có thể chuyển sang `FAILED` theo transition policy. Maximum workflow iterations, repair iterations và retrieval retries bảo đảm quá trình dừng hữu hạn.

## Hướng mở rộng

Phase 2 đặt controlled MCP tools sau workspace policy và approval gate. Phase 3 bổ sung repository index/retrieval có citation. Phase 4 mới kết nối LLM, retriever và MCP thành agent loop hoàn chỉnh.
