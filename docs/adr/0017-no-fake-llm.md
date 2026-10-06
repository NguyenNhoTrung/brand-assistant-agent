# ADR-0017: Không có chế độ fake LLM — luôn dùng OpenAI thật

- Trạng thái: accepted (thay thế ADR 015 trong ARCHITECTURE_DEMO.md §24 và §13.5)
- Ngày: 2026-10-06

## Bối cảnh
Thiết kế ban đầu có `LLM_MODE=fake` cho test/CI. Quyết định: chỉ dùng model thật, API key do người dùng cung cấp.

## Quyết định
- Bỏ `LLM_MODE` và `llm/fake.py`. `llm/client.py` luôn tạo `ChatOpenAI` theo alias trong `config/models.yaml`.
- `OPENAI_API_KEY` bắt buộc: worker và ingest dừng ngay lúc khởi động nếu thiếu; compose báo lỗi nếu `.env` không có key.
- Test gọi LLM gắn `@pytest.mark.llm`, tự bỏ qua khi chưa có key (`make test-llm` để chạy).
  Test không gọi LLM (gateway, Lua, publisher, cancel…) vẫn chạy mọi lúc (Redis dùng fakeredis).
- CI: lint + test không-LLM chạy mọi PR; smoke/eval (tốn tiền) chỉ chạy trên `main` hoặc bấm tay, dùng secret `OPENAI_API_KEY`.

## Hệ quả / Đánh đổi
- Hành vi test sát thực tế; không phải bảo trì kịch bản fake.
- Test LLM tốn chi phí, chậm hơn và không deterministic → assert theo tính chất (có câu trả lời, citation hợp lệ), không so khớp chuỗi.
- PR không chạy smoke E2E.
