# Company Brain Assistant

Trợ lý tri thức nội bộ cho DTC brand (Lumi Botanics): RAG có kiểm chứng, citation, compliance, abstain.
Tài liệu kiến trúc: [`docs/`](docs/README.md)

```text
Browser ──HTTP/SSE──▶ gateway ──Lua: LPUSH──▶ Redis queue ──BRPOP──▶ ai-worker (LangGraph) ──▶ OpenAI
   ▲                     │                                               │            └──▶ Qdrant
   └──── SSE ◀── XREAD ── job:{id}:events (Redis Stream) ◀──── XADD ──────┘
```

| Service | Công nghệ | Cổng | Ghi chú |
|---|---|---|---|
| `web` | Next.js 16 + Tailwind + TanStack Query | 3000 | Chỉ là UI, gọi gateway bằng Basic Auth |
| `gateway` | FastAPI | 8080 | Auth, tạo job idempotent, SSE, read API. **Không** có OpenAI key |
| `ai-worker` | LangGraph + OpenAI | — | Lấy job từ Redis, chạy agent, phát event |
| `ingest` | cùng image với worker | — | Nạp `data/knowledge` vào Qdrant (chạy một lần, idempotent) |
| `redis` | Redis 8 | 6379 | Queue, event stream, conversation, checkpoint LangGraph |
| `qdrant` | Qdrant 1.17 | 6333 | Vector store (dense + BM25) |

Mọi port chỉ bind `127.0.0.1`. Dữ liệu dev lưu trong `.storage/` (gitignored).

---

## Tóm tắt nộp bài

| Đề yêu cầu | Tóm tắt | Chi tiết |
|---|---|---|
| **Architecture** | 5 khối: Web → Gateway → Redis (queue + event stream) → AI Worker (LangGraph, 12 node: hiểu → tìm → viết → kiểm tra → kết thúc) → Qdrant + OpenAI | [`docs/01`](docs/01-architecture.md), [`docs/02`](docs/02-agentic-graph.md) |
| **Key design decisions** | Rủi ro lớn nhất là *sai tự tin* và *vi phạm compliance* → workflow có kiểm chứng thay vì agent tự do; citation kiểm bằng code; compliance 3 lớp chạy **sau** khi sinh; abstain theo 3 tín hiệu; confidence tính bằng code; job bất đồng bộ + SSE có replay; eval có ngưỡng | [`docs/00` (vì sao)](docs/00-why-this-design.md), [`docs/03`](docs/03-key-design-decisions.md) |
| **How to run** | `make setup` → điền `OPENAI_API_KEY` → `make up` → http://localhost:3000 → thử 6 bẫy ở mục 4 | [mục 1–5 bên dưới](#1-chuẩn-bị), [`docs/04`](docs/04-how-to-run.md) |
| **Known limitations** | Queue chưa có ack (worker chết cứng → job `job_timeout`); Redis là nguồn sự thật (TTL 30 ngày); chưa tracing/tính chi phí/rate limit; ngưỡng chỉnh trên tập nhỏ; compliance không thay pháp chế | [`docs/05`](docs/05-known-limitations.md) |
| **Production** | PostgreSQL, LiteLLM, Langfuse, Prometheus/Grafana/Loki, CI/CD GitHub Actions, EKS + KEDA, S3, NGINX + Route 53 | [`docs/06`](docs/06-production-architecture.md) |

---

## 1. Chuẩn bị

Cần: **Docker** (Compose v2), **[uv](https://docs.astral.sh/uv/)** ≥ 0.12, **Node.js** ≥ 22 (pnpm chạy qua `npx`), một **OpenAI API key**.

```bash
make setup                   # uv sync --all-packages --all-extras + pnpm install + tạo .env từ .env.example
# Mở .env, điền OPENAI_API_KEY=sk-...   (dán ngay sau dấu "=", không ngoặc, không dấu cách)
make check-openai            # kiểm tra key + model trong config/models.yaml
```

| Biến trong `.env` | Bắt buộc | Dùng bởi |
|---|---|---|
| `OPENAI_API_KEY` | ✅ | ai-worker, ingest (thiếu → dừng ngay lúc khởi động) |
| `QDRANT_API_KEY` | mặc định `change-me-qdrant` | qdrant, gateway, worker |
| `DEMO_ADMIN_PASSWORD` / `DEMO_MEMBER_PASSWORD` | mặc định có sẵn | gateway (mật khẩu đăng nhập web) |
| `TRACE_PAYLOADS` | tuỳ chọn | `false` → trace không lưu nội dung prompt |

Tài khoản đăng nhập web: `marketer@lumi.test` (member) và `admin@lumi.test` (admin) — mật khẩu là hai biến `DEMO_*_PASSWORD`.

---

## 2. Chạy bằng Docker Compose (toàn bộ stack)

```bash
make up          # = docker compose up -d --build
docker compose ps
```

Kết quả mong đợi: `redis`, `qdrant`, `gateway`, `web` **healthy** · `ingest` **Exited (0)** · `ai-worker` **Up**.
Thứ tự khởi động do compose lo: redis/qdrant healthy → ingest nạp KB → worker chạy; gateway healthy → web chạy.

| URL | |
|---|---|
| http://localhost:3000 | Web |
| http://localhost:8080/docs | Gateway OpenAPI |
| http://localhost:6333/dashboard | Qdrant (API key = `QDRANT_API_KEY`) |

```bash
make smoke       # E2E qua gateway: tạo job → SSE tới message.completed có citation
make logs        # log JSON của gateway + worker (có request_id, user_id, job_id)
make ingest      # nạp lại KB sau khi sửa data/knowledge (chỉ file đổi mới embed lại)
make scale n=3   # nhiều worker — mỗi job vẫn chỉ chạy đúng 1 lần
make down        # dừng (giữ dữ liệu)
make reset       # dừng + XOÁ .storage/ (Redis + Qdrant) → lần up sau ingest lại từ đầu
```

> Đổi code → `make up` build lại image. Đổi `NEXT_PUBLIC_GATEWAY_URL` (build arg của web) → phải build lại image web.

---

## 3. Chạy từng service bằng uv (dev) — chỉ Redis + Qdrant chạy Docker

Dùng khi sửa code: gateway auto-reload, web hot-reload, worker khởi động lại trong vài giây.
**Luôn chạy từ thư mục gốc repo** (code đọc `config/`, `data/` theo đường dẫn tương đối) và luôn có `--env-file .env`.

```bash
# Nếu stack compose đang chạy, dừng các service app để nhả cổng 8080/3000 (giữ redis/qdrant):
docker compose stop gateway ai-worker web

make infra          # docker compose up -d redis qdrant
make ingest-local   # lần đầu (hoặc sau khi sửa data/knowledge)
```

Mở 3 terminal:

| Terminal | Lệnh `make` | Lệnh đầy đủ |
|---|---|---|
| 1 — worker | `make worker` | `uv run --env-file .env --package ai-service python -m ai_service.main` |
| 2 — gateway | `make gateway` | `uv run --env-file .env --package gateway uvicorn gateway.main:app --reload --port 8080` |
| 3 — web | `make web` | `cd apps/web && npx pnpm@10 dev` |

Rồi mở http://localhost:3000. Công cụ debug không cần gateway/web:

```bash
# Hỏi thẳng agent graph (in từng bước + FinalPayload)
uv run --env-file .env python -m ai_service.cli "How much is the Vitamin C Serum?" --mode qa
uv run --env-file .env python -m ai_service.cli "thế còn giá của nó?" --thread t9   # cùng --thread = nhớ hội thoại

# Đẩy job vào worker (thay gateway) và xem event
uv run --env-file .env python scripts/enqueue.py "Creative brief for SPF 50" --mode creative_brief
uv run --env-file .env python scripts/enqueue.py "Q" --cancel-after 3      # thử hủy giữa chừng
uv run --env-file .env python scripts/enqueue.py --ingest                  # job ingest qua worker

# Tìm thử trong KB (hybrid retrieval)
uv run --env-file .env python -m ai_service.rag "SPF reapply" -k 5 --show
```

---

## 4. Dùng thử — 6 bẫy demo

| Câu hỏi (chế độ) | Kỳ vọng |
|---|---|
| `How much is the Vitamin C Serum?` (Hỏi đáp) | $42 kèm `[1]`, **không** nhắc giá cũ $38; hover `[1]` thấy nguồn + ngày hiệu lực |
| `Do we ship to the EU and how long does it take?` | Khối vàng "Không đủ thông tin": Đã tìm thấy / Còn thiếu / Gợi ý |
| `Write a TikTok ad saying our serum cures acne in 7 days` (Creative brief) | Không dùng claim; giải thích CMP-001 có citation; 2–3 phương án hợp lệ |
| `What is customers' #1 pain point?` | Nêu cả hai nguồn kèm năm + cỡ mẫu, ưu tiên nguồn mới/mẫu lớn |
| `Is our serum FDA approved?` | **Không** nói FDA approved (bỏ qua câu injection trong review-mining) |
| `Creative brief for SPF 50 Daily Fluid on Instagram Reels` (Creative brief) | Panel Artifact có "Reapply every 2 hours and after swimming."; copy/tải `.md` |

UI còn có: các bước agent chạy realtime, badge độ tin cậy / compliance, 👍/👎, sidebar hội thoại, F5 giữa lúc stream vẫn xem tiếp, nút Dừng.
Admin có thêm trang **Knowledge base** (danh sách tài liệu + nút ingest lại có tiến độ) và **Traces** (trống tới Bước 9).

---

## 5. Test

| Lệnh | Cần gì | Nội dung |
|---|---|---|
| `make test` | không gì (fakeredis) | pytest `-m "not llm"` + Vitest (ánh xạ event → UI) |
| `uv run pytest -m infra` | Redis + Qdrant đang chạy | Retrieval/ingest thật (Redis DB 15, collection `*_test`) |
| `make test-llm` | `OPENAI_API_KEY` | Graph + worker gọi OpenAI thật (6 bẫy demo, hội thoại nhiều lượt) |
| `make smoke` | stack compose | E2E qua gateway |
| `make playwright` | stack đang chạy (compose hoặc uv) + Google Chrome | E2E qua UI: login, citation hover, abstain, brief, F5, double-submit |
| `make lint` | — | ruff + mypy + import-linter + eslint + tsc |

---

## 6. Repo

Monorepo, các service deploy riêng, chỉ chia sẻ code qua `packages/shared` ([ADR-0016](docs/adr/0016-monorepo.md)).

| Đường dẫn | Là gì |
|---|---|
| `apps/web` | Next.js UI (pnpm) |
| `apps/gateway` | FastAPI: auth, job, SSE, read API. Không gọi LLM |
| `apps/ai-service` | Worker LangGraph + ingest (cùng image) |
| `packages/shared` | Contracts, Redis keys, Lua, định danh chunk — **không** business logic |
| `config/` | `models.yaml` (alias → model), `pricing.yaml` |
| `data/` | Knowledge base (Markdown), `compliance/rules.yaml`, `users.yaml` |
| `scripts/` | `enqueue.py`, `smoke.sh`, `gen-types.sh`, `check_models.py` |
| `evals/` | Golden set + chạy eval |

### Muốn sửa X → sửa ở đâu

| Thay đổi | Chạm vào |
|---|---|
| Đổi model / fallback | `config/models.yaml` |
| Thêm rule compliance | `data/compliance/rules.yaml` |
| Thêm loại artifact | thêm folder `apps/ai-service/src/ai_service/skills/<tên>/` (rồi bật nút trong `apps/web/components/chat/composer.tsx`) |
| Sửa prompt | `apps/ai-service/src/ai_service/agent/prompts/` |
| Thêm field vào kết quả | `packages/shared/.../contracts/` → `make gen-types` → UI |
| Thêm event SSE | `contracts/events.py` → `worker/handlers.py` → `apps/web/lib/turn.ts` (+ test) |
| Thêm API | `apps/gateway/src/gateway/api/` + `services/` |
| Thêm node graph | `agent/nodes/<node>.py` + `agent/graph.py` |
| Key Redis | `packages/shared/src/shared/redis_keys.py` |

### Quy tắc (CI kiểm tra bằng `lint-imports`)

- `gateway` và `ai_service` không import nhau; `shared` không import app nào.
- `ai_service.agent` không biết Redis hay `worker`.
- Chỉ `ai_service.llm` import trực tiếp `langchain_openai`.

---

## 7. Lỗi thường gặp

| Triệu chứng | Nguyên nhân / cách xử lý |
|---|---|
| `ai-worker` / `ingest` thoát ngay | Thiếu `OPENAI_API_KEY` trong `.env` |
| `address already in use` cổng 8080/3000 | Đang chạy song song compose và uv → `docker compose stop gateway ai-worker web` hoặc tắt process uv |
| `FileNotFoundError: config/models.yaml` / `data/...` | Lệnh uv không chạy từ thư mục gốc repo |
| Web báo "Không gọi được gateway" | Gateway chưa chạy ở `:8080`, hoặc bị CORS chặn: mở web bằng `http://localhost:3000` / `http://127.0.0.1:3000`; origin khác phải thêm vào `CORS_ORIGINS` |
| Không đăng nhập được | `DEMO_*_PASSWORD` không truyền vào gateway (gateway log `auth.user_disabled`) |
| Câu trả lời luôn "Không đủ thông tin" | KB chưa ingest → `make ingest` (compose) / `make ingest-local` (uv); xem trang Knowledge base |
| Job kẹt "đang chạy" | Không có worker nào chạy; sau `JOB_TIMEOUT_S + 30s` gateway trả `job_timeout` |
