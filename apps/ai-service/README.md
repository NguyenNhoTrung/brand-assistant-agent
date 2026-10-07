# ai-service

Worker lấy job từ `queue:jobs`, chạy LangGraph, phát event vào `job:{id}:events`. Cùng image chạy `ingest`.

```bash
uv run --env-file .env --package ai-service python -m ai_service.main   # cần Redis 8 + Qdrant + OPENAI_API_KEY
docker compose up -d --build ai-worker                                  # hoặc chạy trong container (1 worker)

# Đẩy job thay gateway, in event tới khi kết thúc (scripts/enqueue.py --help)
uv run --env-file .env python scripts/enqueue.py "How much is the Vitamin C Serum?" --mode qa
uv run --env-file .env python scripts/enqueue.py "thế còn giá của nó?" --conv <conversation_id>
uv run --env-file .env python scripts/enqueue.py "Creative brief for SPF 50" --mode creative_brief --cancel-after 3
uv run --env-file .env python scripts/enqueue.py --ingest [--recreate]

uv run pytest apps/ai-service -m "not llm"               # không gọi OpenAI (Redis dùng fakeredis)
uv run pytest apps/ai-service -m llm                     # gọi OpenAI thật
uv run pytest -m infra                                   # cần Redis + Qdrant (collection *_test, Redis DB 15)

# RAG (cần `uv sync --all-packages --all-extras` để có fastembed)
uv run --env-file .env python -m ai_service.rag.ingest --path data/knowledge [--recreate]
uv run --env-file .env python -m ai_service.rag "câu hỏi" [--doc-type product] [-k 5] [--show]
```

| Thư mục | Việc | Được import |
|---|---|---|
| `worker/` | BRPOP loop, chuyển stream LangGraph → event, lưu kết quả | Redis, `agent` |
| `agent/` | Graph, state, node, edge, prompt | **Không** Redis, **không** `worker` |
| `skills/` | Mỗi loại artifact một folder (SKILL.md, schema, retrieval_plan, render, rubric) | |
| `rag/` | Ingest, retriever hybrid, citations | |
| `compliance/` | rules, checker deterministic, LLM checker | |
| `llm/` | `chat(alias)`, `structured(alias, schema)`, `embeddings()`, tracing | **Chỉ chỗ này** import `langchain_openai` |

| Env | Mặc định | |
|---|---|---|
| `OPENAI_API_KEY` | — | bắt buộc, kiểm tra lúc khởi động |
| `REDIS_URL` / `QDRANT_URL` / `QDRANT_API_KEY` / `QDRANT_COLLECTION` | localhost / `kb_chunks` | |
| `WORKER_CONCURRENCY` | 4 | số task BRPOP song song trong một process |
| `JOB_TIMEOUT_S` | 180 | quá hạn → `job.failed {code: job_timeout}` |
| `SHUTDOWN_GRACE_S` | 25 | SIGTERM → chờ job đang chạy; quá hạn → job `failed/job_timeout` |
| `CHECKPOINT_TTL_MIN` | 43200 | TTL checkpoint LangGraph (phút) |
| `KB_DIR` | `data/knowledge` | thư mục job `ingest` đọc |

Đổi model → `config/models.yaml`. Thêm artifact → thêm folder trong `skills/`.
