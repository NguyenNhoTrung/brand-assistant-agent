# Company Brain Assistant

Trợ lý tri thức nội bộ cho DTC brand (Lumi Botanics): RAG có kiểm chứng, citation, compliance, abstain.
Kiến trúc chi tiết: [`ARCHITECTURE_DEMO.md`](ARCHITECTURE_DEMO.md) · Đề bài: [`REQUIREMENTS.md`](REQUIREMENTS.md)

```text
Browser ──HTTP/SSE──▶ gateway ──Lua: LPUSH──▶ Redis queue ──BRPOP──▶ ai-worker (LangGraph) ──▶ OpenAI
   ▲                     │                                               │            └──▶ Qdrant
   └──── SSE ◀── XREAD ── job:{id}:events (Redis Stream) ◀──── XADD ──────┘
```

## Chạy nhanh

```bash
make setup          # uv sync + pnpm install + tạo .env  → điền OPENAI_API_KEY vào .env
make up             # docker compose (worker/ingest dừng ngay nếu thiếu key)
make smoke          # E2E với OpenAI thật: tạo job → đọc SSE tới message.completed
```

| URL | |
|---|---|
| http://localhost:3000 | Web (`marketer@lumi.test` / `admin@lumi.test`, mật khẩu trong `.env`) |
| http://localhost:8080/docs | Gateway OpenAPI |
| http://localhost:6333/dashboard | Qdrant |

## Repo

Monorepo, 3 service deploy riêng, chỉ chia sẻ code qua `packages/shared` ([ADR-0016](docs/adr/0016-monorepo.md)).

| Đường dẫn | Là gì |
|---|---|
| `apps/web` | Next.js UI (pnpm) |
| `apps/gateway` | FastAPI: auth, job, SSE. Không gọi LLM |
| `apps/ai-service` | Worker LangGraph + ingest (cùng image) |
| `packages/shared` | Contracts, Redis keys, Lua — **không** business logic |
| `config/` | `models.yaml` (alias → model), `pricing.yaml` |
| `data/` | Knowledge base (Markdown), `compliance/rules.yaml`, `users.yaml` |
| `evals/` | Golden set + chạy eval |

## Muốn sửa X → sửa ở đâu

| Thay đổi | Chạm vào |
|---|---|
| Đổi model / fallback | `config/models.yaml` |
| Thêm rule compliance | `data/compliance/rules.yaml` |
| Thêm loại artifact | thêm folder `apps/ai-service/src/ai_service/skills/<tên>/` |
| Sửa prompt | `apps/ai-service/src/ai_service/agent/prompts/` |
| Thêm field vào kết quả | `packages/shared/.../contracts/` → `make gen-types` → UI |
| Thêm event SSE | `contracts/events.py` → `worker/handlers.py` → `web/lib/events.ts` |
| Thêm API | `apps/gateway/src/gateway/api/` + `services/` |
| Thêm node graph | `agent/nodes/<node>.py` + `agent/graph.py` |
| Key Redis | `packages/shared/src/shared/redis_keys.py` |

## Quy tắc (CI kiểm tra bằng `lint-imports`)

- `gateway` và `ai_service` không import nhau; `shared` không import app nào.
- `ai_service.agent` không biết Redis hay `worker`.
- Chỉ `ai_service.llm` import trực tiếp `langchain_openai`.

## Lệnh

`make help` — `test` (không gọi LLM) · `test-llm` (OpenAI thật) · `lint` · `fmt` · `gen-types` · `logs` · `ingest` · `scale n=4` · `eval` · `reset`
