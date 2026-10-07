# web

Next.js UI (App Router) + Tailwind + TanStack Query. Chỉ là UI — không gọi LLM, chỉ nói chuyện với gateway.

```bash
npx pnpm@10 install && npx pnpm@10 dev     # http://localhost:3000, cần gateway ở :8080
npx pnpm@10 test                           # Vitest: ánh xạ event SSE → trạng thái lượt trả lời
npx pnpm@10 e2e                            # Playwright (Chrome đã cài) — cần stack đang chạy + OpenAI
npx pnpm@10 lint && npx pnpm@10 typecheck && npx pnpm@10 build
```

| File | Việc |
|---|---|
| `lib/types.gen.ts` | **Sinh tự động** (`make gen-types`) từ `packages/shared/contracts` — không sửa tay |
| `lib/gateway-fetch.ts` · `lib/api.ts` | Mọi request tới gateway (Basic Auth từ `sessionStorage`, 401 → `/login`, lỗi problem+json) |
| `lib/events.ts` | Đọc SSE bằng `fetch` (cần header Authorization) |
| `lib/turn.ts` | Hàm thuần: event → trạng thái một lượt (bước agent, nguồn, bản nháp, artifact, kết quả) — §15.5 |
| `lib/live-jobs.ts` | Job đang stream sống ngoài component: F5/đổi URL không đứt; rớt mạng → resume bằng `Last-Event-ID` |
| `app/(app)/chat/[[...id]]` | Màn hình chính: lịch sử + lượt đang chạy, panel Nguồn / Artifact |
| `app/(app)/knowledge` · `app/(app)/admin/traces` | Trang admin |

`NEXT_PUBLIC_GATEWAY_URL` (mặc định `http://localhost:8080`) được nhúng lúc build.
Giao thức job + SSE dùng hook/store riêng thay cho `ChatTransport` của AI SDK (phương án dự phòng khi AI SDK không hỗ trợ resume theo `Last-Event-ID`).
