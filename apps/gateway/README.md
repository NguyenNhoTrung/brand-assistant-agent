# gateway

Điểm vào duy nhất từ browser. **Không gọi LLM, không có OpenAI key.**

```bash
uv run --package gateway uvicorn gateway.main:app --reload --port 8080   # cần Redis local
uv run pytest apps/gateway                                              # dùng fakeredis
```

| Thư mục | Việc |
|---|---|
| `api/` | Một file cho mỗi nhóm route (mỏng: validate → gọi service) |
| `services/` | Đọc/ghi Redis (job, conversation…) |
| `core/` | Auth (Basic + argon2), lỗi RFC 9457, Redis client |

Env: `REDIS_URL`, `USERS_FILE`, `DEMO_ADMIN_PASSWORD`, `DEMO_MEMBER_PASSWORD`, `CORS_ORIGINS`.
