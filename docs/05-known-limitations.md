# 05 — Known limitations

Hạn chế của **bản đang chạy** (đối chiếu với code, không phải với bản thiết kế). Hướng xử lý ở
[`06-production-architecture.md`](06-production-architecture.md).

## 1. Độ tin cậy & dữ liệu

| Hạn chế | Hệ quả | Hướng xử lý |
|---|---|---|
| Queue dùng `LPUSH`/`BRPOP` — **không có ack** | Worker bị SIGKILL/OOM giữa chừng → job mất khỏi queue, chỉ được gateway đánh dấu `job_timeout` sau `JOB_TIMEOUT_S + 30s`; không tự retry, không DLQ | Redis Streams + consumer group (`XREADGROUP`/`XACK`/`XAUTOCLAIM`) + DLQ, hoặc SQS |
| Redis là nguồn sự thật duy nhất (job, conversation, message, checkpoint) | Không query/report/analytics; TTL 30 ngày rồi mất; không backup point-in-time; RAM là giới hạn | PostgreSQL cho app + conversation + checkpoint |
| Dual-write Qdrant ↔ `kb:manifest` không có transaction | Ingest bị ngắt có thể lệch tạm thời (tự hội tụ khi chạy lại vì manifest ghi sau cùng) | Registry tài liệu trong Postgres, cờ `indexed` |
| Knowledge base là file Markdown mount vào container | Không upload qua UI, không versioning tài liệu gốc | S3 + event-driven ingest |

## 2. Agent & chất lượng

| Hạn chế | Chi tiết |
|---|---|
| Ngưỡng hiệu chỉnh trên tập nhỏ | `MIN_COSINE=0.30`, `SUFFICIENT_COSINE=0.45`, chunk 300–700 token, budget 6k token — chỉnh trên 17 tài liệu / 28 case eval |
| Compliance không thay pháp chế | Regex chỉ bắt pattern đã liệt kê; LLM verifier có thể bỏ sót diễn đạt khéo. Output là bản nháp đã kiểm tra |
| Bản nháp Q&A có thể bị thay | Token stream trước verify; khi revise UI đổi nội dung (`answer.revised`) |
| BM25 tokenizer tiếng Anh | Câu hỏi tiếng Việt dựa vào nhánh dense + `text_en` do LLM dịch |
| Không có reranker | Thứ hạng chỉ từ RRF |
| Chỉ có 1 skill | `creative_brief`; `insight_summary`, `campaign_recommendation`, `compliance_review` mới có intent, chưa có folder skill → rơi về Q&A |
| Judge cùng họ model | Eval dùng OpenAI cho cả generator và judge |
| Không human-in-the-loop | Brief không có bước duyệt trước khi lưu |

## 3. Vận hành

| Hạn chế | Chi tiết |
|---|---|
| **Chưa có tracing LLM** | `traces:recent` / `trace:{job_id}` được gateway đọc nhưng worker chưa ghi (`llm/client.py`: `TODO(P0): tracing.JobTracer · pricing`) → trang admin Traces trống |
| **Chưa tính chi phí** | `config/pricing.yaml` toàn giá 0; không có budget theo user |
| Chưa có metrics | Không có `/metrics`, không Prometheus/Grafana; chỉ có log JSON (structlog, có `job_id`, `user_id`, `request_id`) ra stdout |
| Không rate limit / concurrency limit | Gateway chỉ có idempotency; một user có thể đẩy nhiều job tuỳ ý |
| Auth là Basic Auth | User trong `users.yaml`, mật khẩu từ env; credential lưu phía browser và gửi mỗi request; không SSO, không refresh/revoke |
| `NEXT_PUBLIC_GATEWAY_URL` bake lúc build | Đổi domain phải build lại image web |
| Không có CD | CI chỉ lint/test/build + smoke trên `main`; không push image, không deploy |
| Chỉ chạy local | Port bind `127.0.0.1`, không TLS, không reverse proxy |

## 4. Bảo mật

- Không phân quyền theo tài liệu; single-tenant — mọi user thấy mọi tài liệu.
- Không PII redaction trước khi gửi prompt cho OpenAI.
- `TRACE_PAYLOADS=true` mặc định (khi có tracing sẽ lưu nguyên văn prompt).
- Qdrant API key dùng chung cho gateway (đọc) và worker (ghi).
