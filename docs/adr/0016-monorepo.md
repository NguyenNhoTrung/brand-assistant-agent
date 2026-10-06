# ADR-0016: Monorepo, 3 service ứng dụng, ranh giới bằng import-linter

- Trạng thái: accepted
- Ngày: 2026-10-06

## Bối cảnh
Một tính năng thường chạm cả contract, gateway, worker và web (ví dụ thêm field vào `FinalPayload`).
Team nhỏ, thời gian làm demo ngắn.

## Quyết định
- Một repo: uv workspace (`packages/shared`, `apps/gateway`, `apps/ai-service`) + `apps/web` (pnpm).
- Service deploy riêng: `web`, `gateway`, `ai-worker` (N replica); `ingest` dùng chung image với worker.
- RAG, compliance, LLM là **module** trong `ai-service`, không phải service mạng.
- Service chỉ giao tiếp qua Redis (queue, stream) và HTTP; chỉ chia sẻ code qua `packages/shared`
  (contracts, Redis keys, Lua), được kiểm tra bằng `.importlinter` trong CI.

## Phương án đã cân nhắc
Polyrepo (mỗi service một repo); tách RAG/compliance thành service riêng.

## Hệ quả / Đánh đổi
- 1 PR cho thay đổi xuyên service; sai contract là CI báo ngay; `make up` chạy tất cả.
- CI phải lọc theo path để không chạy thừa.
- Khi cần tách module thành service, ranh giới import đã sẵn.
