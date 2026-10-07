# Eval ai-service

Đo **độ chính xác** của agent: chạy golden set thẳng vào LangGraph graph của ai-service (không qua worker/gateway).

```bash
make infra && make ingest-local          # Redis + Qdrant, KB đã nạp
make eval                                # toàn bộ golden set → evals/reports/<timestamp>.{md,json}
make eval ARGS="--only qa-,abs-"         # lọc theo id/tiền tố
make eval ARGS="--no-judge"              # chỉ metric deterministic (không gọi LLM judge)
make eval-baseline                       # chép report mới nhất thành evals/reports/baseline.json
```

| File | Vai trò |
|---|---|
| `golden_set.jsonl` | Case: `q`, `mode`, `expected_sources`, `expected_facts`, `forbidden_facts`, `should_abstain`, `forbidden_patterns`, `expected_rule_refs` |
| `run_eval.py` | Chạy graph, chấm từng case, tổng hợp metric, so ngưỡng + baseline |
| `judges.py` | LLM judge (`chat-default`): fact fallback, forbidden claim, rubric artifact |
| `thresholds.yaml` | Ngưỡng §19.3 — dưới ngưỡng → exit 1 |
