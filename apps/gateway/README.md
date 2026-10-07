# gateway

Điểm vào duy nhất từ browser. **Không gọi LLM, không có OpenAI key.**

```bash
uv run --env-file .env --package gateway uvicorn gateway.main:app --reload --port 8080   # cần Redis + Qdrant
docker compose up -d --build gateway                                                   # hoặc trong container
uv run pytest apps/gateway                                                              # fakeredis + Qdrant giả
./scripts/smoke.sh                                                                      # E2E: gateway + worker đang chạy
```

OpenAPI: http://localhost:8080/docs

| Nhóm | Endpoint | Quyền |
|---|---|---|
| auth | `GET /auth/me` | user |
| jobs | `POST /v1/jobs` (header `Idempotency-Key`) · `GET /v1/jobs/{id}` (kèm `result` khi xong) · `POST /v1/jobs/{id}/cancel` | owner |
| events | `GET /v1/jobs/{id}/events` — SSE, `Last-Event-ID`, heartbeat 15 s; stream hết hạn → dựng lại event kết thúc từ `msg:{id}` | owner |
| conversations | `GET /v1/conversations` · `/{id}/messages` · `/{id}/active-job` | owner |
| feedback | `POST /v1/messages/{id}/feedback` `{rating: 1\|-1, comment?}` | owner |
| sources | `GET /v1/sources/{chunk_id}` — encode `#` thành `%23` | user |
| admin | `POST /admin/ingest` · `GET /admin/kb` · `GET /admin/traces` · `GET /admin/jobs/{id}/trace` | admin |
| health | `GET /healthz` · `GET /readyz` (Redis + Qdrant) | — |

Tài nguyên của user khác → `404` (không lộ sự tồn tại). Lỗi dạng `application/problem+json` có `code` + `request_id`.

| Thư mục | Việc |
|---|---|
| `api/` | Một file cho mỗi nhóm route (mỏng: validate → gọi service) |
| `services/` | Đọc/ghi Redis (job, conversation, message) |
| `core/` | Auth (Basic + argon2), lỗi RFC 9457, middleware request id + log JSON, Redis/Qdrant client |

Env: `REDIS_URL`, `QDRANT_URL`, `QDRANT_API_KEY`, `QDRANT_COLLECTION`, `USERS_FILE`, `DEMO_ADMIN_PASSWORD`,
`DEMO_MEMBER_PASSWORD` (thiếu cả hai → không khởi động), `CORS_ORIGINS`, `JOB_TIMEOUT_S`, `SSE_BLOCK_MS`.
