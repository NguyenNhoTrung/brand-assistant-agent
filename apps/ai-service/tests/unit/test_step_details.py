from ai_service.worker.step_details import MAX_ITEMS, MAX_TEXT, describe

EV = {"source_path": "products/serum.md", "title": "Serum", "section": "Price", "doc_type": "product"}


def _labels(detail: list[dict]) -> list[str]:
    return [d["label"] for d in detail]


def test_route_shows_intent_doc_types_and_products():
    label, detail = describe("route", {"route": {"intent": "qa", "doc_types": ["product"], "product_refs": ["Serum"]}})
    assert label == "Hiểu yêu cầu: qa · product"
    assert {"label": "Sản phẩm được nhắc tới", "value": ["Serum"], "md": False} in detail
    assert "Cần hỏi lại" not in _labels(detail)  # needs_clarification không bật → bỏ dòng


def test_plan_lists_queries_with_english_and_filter():
    q = {"text": "giá serum", "text_en": "serum price", "doc_types": ["product"]}
    label, detail = describe(
        "plan_retrieval", {"question": "Giá serum?", "queries": [q], "plan_slots": {"product": None}}
    )
    assert label == "Lập kế hoạch: 1 truy vấn"
    rows = {d["label"]: d["value"] for d in detail}
    assert rows["Truy vấn"] == ["giá serum · EN: serum price · lọc: product"]
    assert "Thông tin trích ra" not in rows  # slot rỗng


def test_retrieve_and_grade_list_sources():
    ev = [{**EV, "sid": f"S{i}"} for i in (1, 2)]
    label, detail = describe("retrieve", {"evidence": ev, "max_cosine": 0.6123, "retrieval_attempts": 1})
    assert label == "Tìm thấy 2 đoạn từ 1 tài liệu"
    rows = {d["label"]: d["value"] for d in detail}
    assert rows["Các đoạn tìm được (xếp theo độ liên quan)"][0] == "S1 · Serum — Price (product)"
    assert rows["Độ tương đồng cao nhất (cosine)"] == "0.61"

    grade = {"status": "partial", "covered_aspects": ["price"], "missing_aspects": ["EU shipping"]}
    label, detail = describe("grade_evidence", {"grade": grade, "evidence": ev[:1]})
    assert label == "Bằng chứng: một phần · giữ 1 đoạn"
    assert {"label": "Khía cạnh còn thiếu", "value": ["EU shipping"], "md": False} in detail


def test_draft_is_markdown_and_verify_lists_issues():
    _, detail = describe("generate_answer", {"draft_md": "Giá **$42** [S1]"})
    assert detail == [{"label": "Bản nháp (trước kiểm tra)", "value": "Giá **$42** [S1]", "md": True}]

    issue = {"severity": "block", "rule_id": "CMP-001", "kind": "compliance", "excerpt": "cures acne", "fix_hint": "bỏ"}
    label, detail = describe("verify", {"verification": {"passed": False, "issues": [issue], "llm_checked": False}})
    assert label == "Kiểm tra: 1 vấn đề cần sửa"
    rows = {d["label"]: d["value"] for d in detail}
    assert rows["Vấn đề"] == ["[block] CMP-001: “cures acne” → bỏ"]
    assert rows["Lớp kiểm tra"] == "chỉ rules — LLM verifier lỗi"


def test_abstain_and_finalize():
    note = {
        "found": [{"text": "Chỉ ship nội địa Mỹ", "source_ids": ["S1"]}],
        "missing": ["EU"],
        "suggestion": "Hỏi Ops",
    }
    _, detail = describe("abstain", {"abstain": note})
    assert {"label": "Đã tìm thấy trong KB", "value": ["Chỉ ship nội địa Mỹ [S1]"], "md": False} in detail

    final = {"status": "answered", "confidence": "high", "citations": [{}], "compliance": {"passed": True}}
    label, detail = describe("finalize", {"final": final})
    assert label == "Hoàn tất: đã trả lời"
    assert {"label": "Số trích dẫn", "value": "1", "md": False} in detail


def test_long_values_are_truncated_and_unknown_node_is_safe():
    _, detail = describe("generate_answer", {"draft_md": "x" * (MAX_TEXT + 50)})
    assert len(detail[0]["value"]) == MAX_TEXT + 1 and detail[0]["value"].endswith("…")
    _, detail = describe("retrieve", {"evidence": [{**EV, "sid": f"S{i}"} for i in range(MAX_ITEMS + 3)]})
    assert detail[0]["value"][-1] == "… và 3 mục khác"
    assert describe("mystery_node", {"x": 1}) == ("mystery_node", [])
