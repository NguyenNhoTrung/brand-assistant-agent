# web

Next.js UI. Chỉ là UI — không gọi LLM.

```bash
npx pnpm@10 install && npx pnpm@10 dev     # http://localhost:3000, cần gateway ở :8080
```

- `lib/types.gen.ts`: **sinh tự động** (`make gen-types`) từ `packages/shared/contracts` — không sửa tay.
- `lib/gateway-fetch.ts`: mọi request tới gateway đi qua đây (gắn Basic Auth, xử lý 401).
- `lib/events.ts`: đọc SSE của job.

TODO(P0): AI SDK `useChat` + `ChatTransport`, AI Elements (citation hover, steps, artifact panel), sidebar.
