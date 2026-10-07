# 03 — Key design decisions

Mỗi quyết định gắn với một yêu cầu của đề bài. ADR chi tiết: `docs/adr/`.

| # | Quyết định | Lý do | Đánh đổi |
|---|---|---|---|
| 1 | **LangGraph workflow có điều kiện** (corrective RAG + verify/revise), không ReAct/tool-calling | Các bước biết trước → dễ test (edges là hàm thuần), rẻ, hành vi ổn định; không có dữ liệu live cần tool | Ít linh hoạt nếu sau này cần tool (Shopify, Meta Ads) → thêm subgraph riêng |
| 2 | **Async job + event stream per job + SSE** thay vì HTTP streaming trực tiếp | Gateway tách khỏi worker; F5/rớt mạng replay được bằng `Last-Event-ID`; client mở SSE *sau* khi worker đã chạy vẫn không lỡ event (khác Redis Pub/Sub) | Thêm một hop Redis; event chỉ giữ 1 giờ |
| 3 | **Gateway không có OpenAI key, không import `ai_service`** (import-linter) | Biên hệ thống chỉ lo auth/quota/vòng đời job; lộ gateway không lộ khả năng gọi model | Phải đồng bộ contract qua `packages/shared` + `make gen-types` |
| 4 | **Tạo job bằng một Lua script** (idempotency + HSET + LPUSH nguyên tử) | Double-submit/retry mạng không tạo 2 job; không có khe hở "đã ghi job nhưng chưa vào queue" | Logic nằm trong Lua (khó đọc hơn Python) |
| 5 | **Redis là nguồn sự thật duy nhất** (job, conversation, checkpoint) cho demo | Một dependency, AOF bền đủ cho demo, `make reset` xoá sạch | Không query/report được; TTL 30 ngày; không có migration — xem roadmap Postgres |
| 6 | **Hybrid retrieval trong Qdrant** (dense + BM25, RRF trong một `query_batch_points`) + dense-only top-1 để lấy `max_cosine` | BM25 bắt tên SKU/thuật ngữ chính xác, dense bắt ngữ nghĩa/tiếng Việt; RRF chỉ là thứ hạng nên cần cosine tuyệt đối cho gate abstain | BM25 tokenizer tiếng Anh |
| 7 | **Frontmatter `supersedes` + `status` filter** | Bẫy phiên bản: giá cũ không bao giờ vào context, thay vì hy vọng LLM tự chọn | Người viết tài liệu phải khai báo `supersedes` |
| 8 | **Grounded or abstain với 3 tín hiệu** (cosine gate, LLM grading, độ phủ doc_type) | "Nói rõ khi không đủ thông tin" một cách có hệ thống, có lượt retrieve lại với query viết lại | Ngưỡng 0.30/0.45 chỉnh trên tập nhỏ |
| 9 | **Confidence deterministic** từ grade + verify + số lần revise | LLM tự chấm độ chắc chắn không đáng tin | Chỉ 3 mức thô |
| 10 | **Compliance 3 lớp** (prompt → regex theo field → LLM verifier có grounding) + revise ≤ 2 | Compliance by construction, không by prompt; verifier bị lọc ảo giác (excerpt phải có thật, severity lấy từ YAML) | Regex chỉ bắt pattern đã liệt kê; output vẫn là *bản nháp đã kiểm tra* |
| 11 | **Rules là dữ liệu** (`data/compliance/rules.yaml`) + bản cho người đọc trong KB | Pháp chế sửa rule không cần sửa code; rule vẫn **trích dẫn** được | Phải giữ 2 file đồng bộ |
| 12 | **Citation `[S#]` → `[n]` resolve deterministic** ở `finalize` | Validator kiểm được; UI hover thấy nguồn + ngày hiệu lực; marker sai bị bắt ở verify | Model đôi khi chèn marker sai chỗ → `normalize_artifact` |
| 13 | **Skills pattern** cho artifact (SKILL.md + schema + retrieval plan + rubric + template) | Thêm loại output không sửa graph | Mỗi skill cần schema strict (OpenAI strict: không default) |
| 14 | **Q&A stream bản nháp, artifact không stream token** | TTFT thấp cho hỏi đáp; artifact có thể bị copy đi chạy ads nên không được lộ bản vi phạm | Người dùng có thể thấy bản nháp Q&A bị thay |
| 15 | **Model alias theo vai trò** (`chat-fast/default/strong`, `embed`) trong `config/models.yaml`, fallback 1 bước | Đổi model bằng config; model nhỏ cho phân loại, lớn chỉ cho artifact | Chưa có LiteLLM → chưa có spend tracking/budget |
| 16 | **Một tầng retry LLM duy nhất** (SDK `max_retries=2`), retry hạ tầng ở `RetryPolicy` của node, không retry cả job | Tránh nhân retry (3×3×3) gây bão request và tốn tiền | Job lỗi giữa chừng phải submit lại |
| 17 | **Không có fake LLM** (ADR-0017) | Test sát thực tế; không bảo trì kịch bản giả | Test LLM tốn tiền, không deterministic → assert theo tính chất; PR không chạy smoke |
| 18 | **Monorepo + import-linter** (ADR-0016) | Một PR cho thay đổi xuyên service; ranh giới service được kiểm bằng CI | CI phải lọc theo path |
| 19 | **Cache embedding trong Redis** (`emb:{model}:{sha256}`) + ingest idempotent theo `content_hash` | Ingest lại / mất Qdrant dựng lại không tốn tiền OpenAI | Cache 7 ngày |
| 20 | **Eval có ngưỡng chặn** (`thresholds.yaml`, exit 1) | Đổi prompt/model phải qua golden set; "testable" là tiêu chí của đề | Judge cùng họ model với generator |
