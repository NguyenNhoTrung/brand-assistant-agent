# 01 — Architecture (hiện trạng)

> Mô tả **những gì đang chạy trong repo**.
> Bản production đề xuất: [`06-production-architecture.md`](06-production-architecture.md).
> Đi sâu vào agent: [`02-agentic-graph.md`](02-agentic-graph.md).

---

## 1. Tổng quan (Level 0 — 5 khối lớn)

Company Brain Assistant là trợ lý tri thức nội bộ cho brand DTC giả định **Lumi Botanics**. Toàn hệ thống chỉ có
**5 khối**, đọc từ trái sang phải:

```mermaid
flowchart LR
    U(["👤 Người dùng"])
    WEB["① Web UI<br/>Next.js"]
    GW["② Gateway<br/>FastAPI"]
    R[("③ Redis<br/>hàng đợi + sự kiện + dữ liệu")]
    WK["④ AI Worker<br/>LangGraph agent"]
    KB[("⑤ Knowledge<br/>Qdrant + OpenAI")]

    U --> WEB
    WEB -->|"1. gửi câu hỏi"| GW
    GW -->|"2. tạo job"| R
    R -->|"3. lấy job"| WK
    WK <-->|"4. tìm + sinh câu trả lời"| KB
    WK -->|"5. ghi tiến trình + kết quả"| R
    R -->|"6. đọc sự kiện"| GW
    GW -->|"7. stream SSE"| WEB
```

| Khối | Một câu mô tả |
|---|---|
| ① Web UI | Giao diện chat; gửi câu hỏi, nhận câu trả lời dạng stream, hiển thị citation / artifact |
| ② Gateway | "Cửa vào" duy nhất: xác thực, tạo job, đẩy sự kiện về browser. **Không** gọi LLM |
| ③ Redis | "Bưu điện" giữa gateway và worker: hàng đợi job, luồng sự kiện mỗi job, và lưu hội thoại |
| ④ AI Worker | Nơi agent chạy: hiểu câu hỏi → tìm → viết → kiểm tra compliance → trả kết quả |
| ⑤ Knowledge | Qdrant chứa kiến thức đã index; OpenAI để embed và sinh văn bản |

Vì sao tách như vậy: gateway và worker **không gọi nhau trực tiếp**, chỉ nói chuyện qua Redis → worker chết hay
browser F5 thì job và sự kiện vẫn còn, scale worker độc lập với gateway.

---

## 2. Bên trong từng khối (Level 1)

### 2.1 ① Web UI — `apps/web`

```mermaid
flowchart LR
    subgraph WEB["① Web UI (Next.js)"]
        LOGIN["Trang Login"]
        CHAT["Trang Chat<br/>composer · agent steps · câu trả lời"]
        PANEL["Side panel<br/>nguồn · artifact"]
        SIDEBAR["Sidebar hội thoại"]
        ADMIN["Trang Admin<br/>Knowledge base · Traces"]
        LIB["lib: gateway-fetch · events (SSE) · turn (event → UI)"]
    end
    LOGIN & CHAT & PANEL & SIDEBAR & ADMIN --> LIB -->|HTTP / SSE| GW["② Gateway"]
```

| Thành phần | Việc |
|---|---|
| `lib/gateway-fetch.ts` | Gắn header `Authorization` cho mọi request, 401 → về `/login` |
| `lib/events.ts` | Đọc SSE bằng `fetch` (cần header auth nên không dùng `EventSource`), hỗ trợ `Last-Event-ID` |
| `lib/turn.ts` | Ánh xạ event → trạng thái một lượt chat (token, steps, sources, final) — có test Vitest |
| `components/chat/*` | Citation hover, badge confidence/compliance, artifact panel, feedback 👍/👎 |

### 2.2 ② Gateway — `apps/gateway`

```mermaid
flowchart LR
    IN["Request từ Web"] --> AUTH["Auth<br/>Basic + argon2id"]
    AUTH --> JOB["Jobs API<br/>tạo · xem · hủy"]
    AUTH --> SSE["Events API<br/>SSE relay"]
    AUTH --> READ["Read API<br/>conversations · sources · feedback"]
    AUTH --> ADM["Admin API<br/>ingest · kb · traces"]
    JOB -->|"Lua: tạo job + LPUSH"| R[("③ Redis")]
    SSE -->|"XREAD"| R
    READ --> R
    READ -->|"tra chunk"| QD[("Qdrant")]
    ADM --> R
```

| Thành phần | Endpoint | Ghi chú |
|---|---|---|
| Auth | mọi route | `users.yaml` + mật khẩu từ env, cache verify 5 phút |
| Jobs API | `POST /v1/jobs`, `GET /v1/jobs/{id}`, `POST /v1/jobs/{id}/cancel` | `Idempotency-Key` bắt buộc → bấm 2 lần không tạo 2 job |
| Events API | `GET /v1/jobs/{id}/events` | Replay từ đầu / từ `Last-Event-ID`, heartbeat 15 s, tự phát hiện job kẹt |
| Read API | `/v1/conversations…`, `/v1/sources/{chunk_id}`, `/v1/messages/{id}/feedback` | Lọc theo `user_id`, trả 404 thay vì 403 |
| Admin API | `/admin/ingest`, `/admin/kb`, `/admin/traces` | Chỉ role `admin` |

### 2.3 ③ Redis — nhóm dữ liệu

```mermaid
flowchart TB
    subgraph R["③ Redis 8 (AOF)"]
        Q[("Hàng đợi<br/>queue:jobs")]
        EV[("Sự kiện mỗi job<br/>job:{id}:events")]
        APP[("Dữ liệu app<br/>job · conversation · message")]
        CK[("Bộ nhớ agent<br/>LangGraph checkpoint")]
        CACHE[("Cache<br/>embedding · kb manifest")]
    end
```

Chi tiết từng key: [mục 5](#5-data-model-redis-là-nguồn-sự-thật-duy-nhất-ở-bản-demo).

### 2.4 ④ AI Worker — `apps/ai-service`

```mermaid
flowchart LR
    R[("③ Redis")] -->|BRPOP| LOOP["Worker loop<br/>timeout · hủy · tắt êm"]
    LOOP --> H{"Loại job"}
    H -->|chat| GRAPH["LangGraph agent<br/>12 node"]
    H -->|ingest| ING["Ingest pipeline"]
    GRAPH --> PUB["Event publisher"] -->|XADD| R
    GRAPH --> STORE["Lưu kết quả"] --> R
```

Bên trong `LangGraph agent` có 4 module hỗ trợ:

```mermaid
flowchart LR
    G["LangGraph agent"] --> RAG["RAG<br/>tìm kiếm hybrid"]
    G --> CMP["Compliance<br/>rules · regex · LLM verifier"]
    G --> SK["Skills<br/>creative_brief"]
    G --> LLM["LLM client<br/>alias → model + fallback"]
    RAG --> QD[("Qdrant")]
    LLM --> OAI(("OpenAI"))
```

| Module | Code | Việc |
|---|---|---|
| Worker loop | `worker/loop.py` | N task song song (`WORKER_CONCURRENCY=4`), timeout 180 s, SIGTERM chờ 25 s |
| Handlers | `worker/handlers.py` | Chạy graph, chuyển stream LangGraph → event hệ thống |
| Publisher | `worker/publisher.py` | Gộp token mỗi ~50 ms trước khi ghi Redis |
| Agent | `agent/` | 12 node — xem [`02-agentic-graph.md`](02-agentic-graph.md) |
| RAG | `rag/` | Hybrid dense + BM25, dựng context có citation `S1..Sn`, ingest |
| Compliance | `compliance/` | Rule từ `data/compliance/rules.yaml` |
| Skills | `skills/` | Mỗi loại artifact là một folder |
| LLM client | `llm/client.py` | Điểm **duy nhất** tạo model; alias trong `config/models.yaml` |

### 2.5 ⑤ Knowledge — Qdrant + OpenAI + Ingest

```mermaid
flowchart LR
    MD["data/knowledge/*.md<br/>17 tài liệu"] --> ING["Ingest<br/>chunk → embed → upsert"]
    ING -->|embed| OAI(("OpenAI<br/>text-embedding-3-small"))
    ING --> QD[("Qdrant · kb_chunks<br/>dense + BM25")]
    WK["④ Worker"] -->|"tìm kiếm"| QD
    WK -->|"chat / structured output"| OAI2(("OpenAI<br/>gpt-5.4 nano · mini · full"))
```

### 2.6 Bảng công nghệ

| Service | Công nghệ | Code |
|---|---|---|
| `web` | Next.js 16, Tailwind, TanStack Query, `eventsource-parser` | `apps/web` |
| `gateway` | FastAPI, redis-py async, sse-starlette, argon2 | `apps/gateway` |
| `ai-worker` + `ingest` | LangGraph, langchain-openai, qdrant-client, fastembed (BM25), structlog | `apps/ai-service` |
| `redis` | Redis 8 (AOF `everysec`, `noeviction`, 1 GB) | — |
| `qdrant` | Qdrant 1.17 (API key) | — |
| `packages/shared` | Pydantic: contracts, Redis keys, Lua script, UUIDv7 — không business logic | `packages/shared` |

Ranh giới được CI kiểm bằng `import-linter`: `gateway` ⟂ `ai_service`; `shared` không import app;
`ai_service.agent` không biết Redis/worker; chỉ `ai_service.llm` import `langchain_openai`.

---

## 3. Luồng xử lý

### 3.1 Một lượt chat — nhìn ở mức khối

```mermaid
sequenceDiagram
    autonumber
    actor U as User
    participant W as ① Web
    participant G as ② Gateway
    participant R as ③ Redis
    participant K as ④ Worker

    U->>W: Gõ câu hỏi
    W->>G: POST /v1/jobs
    G->>R: tạo job + đưa vào hàng đợi
    G-->>W: 202 {job_id}
    W->>G: mở SSE /v1/jobs/{id}/events
    K->>R: lấy job
    loop agent chạy từng bước
        K->>R: ghi sự kiện (bước, nguồn, token)
        R-->>G: sự kiện mới
        G-->>W: SSE
    end
    K->>R: lưu câu trả lời + message.completed
    G-->>W: message.completed → đóng stream
    W-->>U: câu trả lời + citation
```

### 3.2 Bên trong ④ Worker cho một job chat

```mermaid
sequenceDiagram
    autonumber
    participant K as Worker
    participant A as LangGraph agent
    participant Q as Qdrant
    participant O as OpenAI
    participant R as Redis

    K->>R: status = running · XADD job.started
    K->>A: astream(câu hỏi, thread_id = conversation_id)
    A->>R: đọc checkpoint (lịch sử hội thoại)
    A->>O: route + plan (model nhỏ)
    A->>Q: tìm hybrid
    A->>O: grade bằng chứng
    A->>O: viết câu trả lời (stream token)
    A->>O: verify compliance + citation
    opt có lỗi (tối đa 2 lần)
        A->>O: revise
    end
    A->>R: lưu checkpoint
    A-->>K: FinalPayload
    K->>R: lưu message (1 transaction) · XADD message.completed
```

Chi tiết từng lệnh Redis (Lua `create_job`, `XREAD BLOCK`, kiểm tra cờ hủy mỗi 200 ms…) nằm trong code
`gateway/api/jobs.py`, `gateway/api/events.py`, `worker/handlers.py`.

### 3.3 Sequence — rớt mạng / F5 giữa lúc stream

```mermaid
sequenceDiagram
    autonumber
    participant W as web
    participant G as gateway
    participant R as Redis

    W->>G: GET /events
    G-->>W: id=171-0 node.completed …
    Note over W: F5 / mất mạng
    W->>G: GET /v1/conversations/{cid}/active-job
    G-->>W: {job_id}
    W->>G: GET /v1/jobs/{id}/events · Last-Event-ID: 171-0
    G->>R: XREAD từ 171-0 (replay phần bị lỡ)
    G-->>W: các event sau 171-0 … message.completed
    alt Stream đã hết hạn (TTL 1h) nhưng job đã xong
        G->>R: HGETALL job:{id} + GET job:{id}:msg → msg:{id}
        G-->>W: dựng lại message.completed / job.failed / job.cancelled
    else Worker chết, job kẹt running > JOB_TIMEOUT_S + 30s
        G->>R: HSET job failed (job_timeout) — phát hiện lazy
        G-->>W: job.failed {code: job_timeout}
    end
```

### 3.4 Sequence — hủy job

```mermaid
sequenceDiagram
    participant W as web
    participant G as gateway
    participant R as Redis
    participant K as ai-worker
    W->>G: POST /v1/jobs/{id}/cancel
    G->>R: SET job:{id}:cancel 1 EX 3600 (no-op nếu job đã kết thúc)
    G-->>W: 202
    K->>R: EXISTS job:{id}:cancel (giữa các chunk của astream)
    K->>K: raise JobCancelled
    K->>R: HSET status=cancelled · nhả conv.active_job_id
    K->>R: XADD job.cancelled
    R-->>G: job.cancelled → SSE → đóng stream
```

### 3.5 Sequence — ingest knowledge base

```mermaid
sequenceDiagram
    autonumber
    participant A as Admin (web) / make ingest
    participant G as gateway
    participant R as Redis
    participant K as ai-worker / ingest container
    participant O as OpenAI
    participant Q as Qdrant

    A->>G: POST /admin/ingest (role=admin)
    G->>R: create_job.lua (type=ingest, không conversation)
    K->>R: BRPOP → SET kb:ingest:lock NX (1 ingest tại 1 thời điểm)
    loop từng file .md trong data/knowledge
        K->>K: parse frontmatter → validate → content_hash
        alt hash trùng kb:manifest
            K-->>R: XADD ingest.progress {action: skipped}
        else mới / đổi
            K->>K: chunk theo heading (300–700 token, overlap 60)
            K->>R: MGET emb cache
            K->>O: embed phần chưa cache
            K->>K: BM25 sparse (fastembed, local)
            K->>Q: upsert point id = uuid5(path#ordinal), xoá ordinal thừa
            K->>R: HSET kb:manifest (ghi SAU CÙNG)
        end
    end
    K->>Q: set status=superseded cho tài liệu bị `supersedes`
    K->>R: DEL lock · XADD message.completed (báo cáo added/updated/skipped/rejected)
```

### 3.6 Vòng đời job

```mermaid
stateDiagram-v2
    [*] --> queued: create_job.lua
    queued --> running: worker BRPOP + mark_running
    queued --> cancelled: cờ cancel có trước khi chạy
    running --> succeeded: save_turn / ingest xong
    running --> failed: lỗi (llm_unavailable, internal_error, job_timeout 180s)
    running --> cancelled: cờ cancel giữa chừng
    running --> failed: SIGTERM quá shutdown_grace_s (25s)
    running --> failed: worker chết cứng → gateway phát hiện stale (job_timeout + 30s)
    succeeded --> [*]
    failed --> [*]
    cancelled --> [*]
```

---

## 4. Event protocol (SSE)

Mỗi frame có `id` = ID entry Redis Stream → client chỉ cần gửi lại `Last-Event-ID`.
Envelope: `{"v":1, "job_id", "ts", "data"}` (`shared.contracts.events`).

| Event | Phát bởi | Ý nghĩa ở UI |
|---|---|---|
| `job.started` | handler | Bắt đầu chạy |
| `node.started` / `node.completed` | node (`emit`) / handler (`updates`) | Danh sách "agent steps" có `label`, `detail`, `duration_ms` |
| `route.decided` | `route` | Intent + doc_types |
| `retrieval.sources` | `retrieve`, sau `grade_evidence` (đánh số lại) | Panel nguồn S1..Sn |
| `token` | `generate_answer`, `revise` | Bản nháp Q&A (artifact **không** stream token) |
| `verification.result` | `verify` | Badge compliance, danh sách issue |
| `answer.revised` | `revise` | UI thay bản nháp bằng bản sửa |
| `artifact.ready` | `finalize` | Panel artifact (JSON + Markdown) |
| `ingest.progress` | ingest handler | Thanh tiến độ trang KB |
| `message.completed` | handler | **Kết quả chính thức** (`FinalPayload`) — terminal |
| `job.failed` / `job.cancelled` | worker / gateway | Terminal |
| `heartbeat` | gateway (mỗi 15 s khi không có event) | Giữ kết nối qua proxy |

---

## 5. Data model (Redis là nguồn sự thật duy nhất ở bản demo)

| Key | Kiểu | Nội dung | TTL |
|---|---|---|---|
| `queue:jobs` | LIST | job_id chờ xử lý (LPUSH / BRPOP) | — |
| `job:{id}` | HASH | `user_id, conversation_id, type, status, input, created_at, started_at, finished_at, error` | 7 ngày |
| `job:{id}:events` | STREAM | Event của job | 1 giờ sau khi kết thúc |
| `job:{id}:cancel` | STRING | Cờ hủy | 1 giờ |
| `job:{id}:msg` | STRING | id message assistant của job | 7 ngày |
| `idem:{uid}:{key}` | STRING | job_id (idempotency) | 24 giờ |
| `user:{uid}:jobs` / `user:{uid}:convs` | ZSET | Danh sách theo thời gian | 7 / 30 ngày |
| `conv:{cid}` | HASH | `user_id, title, updated_at, active_job_id` | 30 ngày |
| `conv:{cid}:msgs` | LIST | message id theo thứ tự | 30 ngày |
| `msg:{id}` | STRING (JSON) | Message + citations, confidence, artifact, compliance, steps, feedback | 30 ngày |
| `checkpoint:*` | (langgraph-checkpoint-redis) | State graph theo `thread_id = conversation_id` | 30 ngày |
| `emb:{model}:{sha256}` | STRING (float32 bytes) | Cache embedding | 7 ngày |
| `kb:manifest` | HASH | `source_path → {content_hash, chunk_count, status, …}` | — |
| `traces:recent`, `trace:{job_id}` | ZSET / STRING | Đọc bởi trang admin Traces (**chưa có writer** — xem limitations) | — |

Qdrant collection `kb_chunks`: point id `uuid5(source_path#ordinal)`, vectors `dense` (1536, cosine) + `bm25`
(sparse, IDF), payload `chunk_id, source_path, title, doc_type, section, content, effective_date, version,
status, product_id, has_clinical_studies, token_count`.

---

## 6. Cấu trúc repo

```text
apps/
  web/                 Next.js UI
  gateway/             FastAPI: api/ (routers) · core/ (auth, errors, redis, middleware) · services/
  ai-service/
    agent/             graph.py · state.py · edges.py · nodes/ · prompts/*.md · schemas.py · confidence.py
    rag/               retriever.py · context_builder.py · citations.py · qdrant_store.py · sparse.py · ingest/
    compliance/        rules.py · deterministic.py · llm_checker.py
    skills/            registry.py · creative_brief/ (SKILL.md, schema.py, retrieval_plan.yaml, rubric.yaml, render.md.j2)
    llm/               client.py (điểm duy nhất tạo model) · config.py · embed_cache.py
    worker/            loop.py · handlers.py · publisher.py · jobs.py · store.py · step_details.py
packages/shared/       contracts/ · redis_keys.py · lua/create_job.lua · ids.py
config/                models.yaml (alias → model) · pricing.yaml
data/                  knowledge/ (17 tài liệu .md) · compliance/rules.yaml · users.yaml
evals/                 golden_set.jsonl (28 case) · run_eval.py · judges.py · thresholds.yaml
.github/workflows/     ci.yml
```
