# ai-service

Worker lấy job từ `queue:jobs`, chạy LangGraph, phát event vào `job:{id}:events`. Cùng image chạy `ingest`.

```bash
uv run --package ai-service python -m ai_service.main   # cần Redis 8 local + OPENAI_API_KEY
uv run pytest apps/ai-service -m "not llm"               # không gọi OpenAI (Redis dùng fakeredis)
uv run pytest apps/ai-service -m llm                     # gọi OpenAI thật
```

| Thư mục | Việc | Được import |
|---|---|---|
| `worker/` | BRPOP loop, chuyển stream LangGraph → event, lưu kết quả | Redis, `agent` |
| `agent/` | Graph, state, node, edge, prompt | **Không** Redis, **không** `worker` |
| `skills/` | Mỗi loại artifact một folder (SKILL.md, schema, retrieval_plan, render, rubric) | |
| `rag/` | Ingest, retriever hybrid, citations | |
| `compliance/` | rules, checker deterministic, LLM checker | |
| `llm/` | `chat(alias)`, `structured(alias, schema)`, `embeddings()`, tracing | **Chỉ chỗ này** import `langchain_openai` |

Đổi model → `config/models.yaml`. Thêm artifact → thêm folder trong `skills/`.
