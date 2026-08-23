# Project Roadmap

OpenRouter Ox Alpha provider and structured-output startup hardening completed
on 2026-08-23: live Responses API, environment-only credential, complete decision
schemas, a mutation-free analysis path, bounded reasoning/output, 150 tests, and 82%
coverage. See the
[completion report](../plans/260823-1730-openrouter-provider/reports/pm-260823-1841-openrouter-provider.md).

Production completion passed on 2026-08-22: bounded retrieval, production AI
providers, executable persisted CLI, 80% coverage gate, wheel smoke, and GitHub
Actions on Python 3.11/3.12. See the
[final acceptance report](../plans/260822-2208-coding-agent-completion/reports/final-260822-coding-agent-acceptance.md).

| Phase | Nội dung | Trạng thái |
|---|---|---|
| 0 | Audit, dọn generated/vendor artifacts, tạo layout tái lập | completed |
| 1 | Task state, workflow, skill routing, LLM boundary, persistence, trace, CLI | completed |
| 2 | Controlled MCP tools và approval policy | completed |
| 3 | Repository RAG, indexing, hybrid retrieval và citations | completed |
| 4 | Agent loop end-to-end | completed |
| 5 | Recovery, checkpoint, resilience và security hardening | completed |
| 6 | Evaluation, benchmark và tài liệu học thuật | completed |
| B2 | Evidence verification, grounded execution, staged debug, typed recovery và verified final report | completed (2026-08-22) |

Không bắt đầu phase kế tiếp chỉ vì phase trước đã code xong. Mỗi phase phải qua test, review và cập nhật tài liệu trước khi được duyệt triển khai tiếp.

Batch 2 đã qua gate cuối B2.6. Chi tiết mapping yêu cầu, commit và regression
nằm trong [Batch 2 Acceptance Report](batch-2-acceptance.md).
