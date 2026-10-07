# Docs — Company Brain Assistant

| # | Tài liệu | Nội dung |
|---|---|---|
| 00 | [Why this design](00-why-this-design.md) | **Đọc trước**: từ rủi ro nghiệp vụ → 6 câu hỏi thiết kế → những gì cố ý không làm |
| 01 | [Architecture](01-architecture.md) | Sơ đồ khối hệ thống hiện tại, sequence diagram (chat, reconnect/F5, cancel, ingest), vòng đời job, event SSE, Redis keys |
| 02 | [Agentic graph](02-agentic-graph.md) | Đi sâu LangGraph: 12 node, state, edges, retrieval, abstain, compliance 3 lớp, skills, streaming, độ tin cậy |
| 03 | [Key design decisions](03-key-design-decisions.md) | 20 quyết định thiết kế kèm lý do và đánh đổi |
| 04 | [How to run the demo](04-how-to-run.md) | Chạy bằng Docker Compose / uv, 6 bẫy demo, test & eval |
| 05 | [Known limitations](05-known-limitations.md) | Hạn chế của bản đang chạy (đối chiếu code) |
| 06 | [Production architecture](06-production-architecture.md) | PostgreSQL, LiteLLM, Langfuse, Prometheus/Grafana/Loki, GitHub Actions CI/CD, EKS + KEDA, S3, NGINX + Route 53, lộ trình P0–P3 |

Tài liệu khác:

- ADR: [`adr/`](adr/) — mẫu `adr/0000-template.md`
