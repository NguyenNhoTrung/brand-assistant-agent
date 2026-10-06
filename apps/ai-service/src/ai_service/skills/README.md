Mỗi skill một folder, `registry.py` tự phát hiện:

```text
skills/<tên>/
├── SKILL.md             # khi nào dùng, cấu trúc, tiêu chuẩn → nạp vào system prompt
├── schema.py            # Pydantic schema cho structured output
├── retrieval_plan.yaml  # query theo từng phần
├── render.md.j2         # artifact → Markdown
└── rubric.yaml          # tiêu chí LLM-as-judge trong eval
```

P0: `creative_brief` · P1: `compliance_review` · P2: `insight_summary`, `campaign_recommendation`.
