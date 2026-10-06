# shared

Chỉ chứa **giao thức** giữa `gateway`, `ai-service` và `web`:

| Module | Nội dung |
|---|---|
| `contracts/` | DTO + event (Pydantic). Nguồn sinh `apps/web/lib/types.gen.ts` (`make gen-types`) |
| `redis_keys.py` | Mọi key Redis — không viết key dạng chuỗi ở chỗ khác |
| `lua/` | Script Lua nguyên tử (`create_job.lua`) |
| `settings_base.py` | Setting dùng chung (Redis, Qdrant, log). Mỗi app kế thừa |
| `ids.py` | UUIDv7, `now_ms()` |

Quy tắc: không import `gateway` hay `ai_service` (kiểm tra bằng `lint-imports`).
