"""Mô tả output của từng bước agent cho người dùng: nhãn kết quả (§7.2) + chi tiết mở rộng trên UI.

Dựng từ state update mà node trả về (stream mode `updates`) — node không cần biết UI tồn tại.
Chi tiết là danh sách `{label, value, md}`; `value` là chuỗi hoặc danh sách chuỗi, `md=True` → render Markdown.
"""

from typing import Any

MAX_TEXT = 2000
MAX_ITEMS = 12

GRADE = {"sufficient": "đủ", "partial": "một phần", "insufficient": "chưa đủ"}
STATUS = {
    "answered": "đã trả lời",
    "partial": "trả lời một phần",
    "abstained": "không đủ thông tin",
    "needs_review": "cần review",
    "clarification": "cần hỏi lại",
    "out_of_scope": "ngoài phạm vi",
}

Detail = list[dict[str, Any]]


def _text(s: Any) -> str:
    s = str(s or "").strip()
    return s if len(s) <= MAX_TEXT else s[:MAX_TEXT] + "…"


def _items(xs: list[Any]) -> list[str]:
    out = [_text(x) for x in xs[:MAX_ITEMS]]
    return [*out, f"… và {len(xs) - MAX_ITEMS} mục khác"] if len(xs) > MAX_ITEMS else out


def _row(label: str, value: Any, *, md: bool = False) -> dict[str, Any] | None:
    if value is None or value == "" or value == []:
        return None
    return {"label": label, "value": _items(value) if isinstance(value, list) else _text(value), "md": md}


def _rows(*rows: dict[str, Any] | None) -> Detail:
    return [r for r in rows if r is not None]


def _source(e: dict[str, Any]) -> str:
    return f"{e['sid']} · {e['title']} — {e.get('section') or '…'} ({e['doc_type']})"


def describe(node: str, u: dict[str, Any]) -> tuple[str, Detail]:
    """→ (nhãn kết quả, chi tiết output) của một bước."""
    match node:
        case "load_context":
            return "Nạp ngữ cảnh hội thoại", _rows(
                _row("Câu hỏi", u.get("question")), _row("Chế độ", u.get("requested_mode"))
            )

        case "route":
            r = u.get("route") or {}
            types = r.get("doc_types") or []
            label = f"Hiểu yêu cầu: {r.get('intent', '?')}" + (f" · {', '.join(types)}" if types else "")
            return label, _rows(
                _row("Ý định", r.get("intent")),
                _row("Loại tài liệu cần tìm", ", ".join(types) or "tất cả"),
                _row("Sản phẩm được nhắc tới", r.get("product_refs")),
                _row("Cần hỏi lại", r.get("clarification_question") if r.get("needs_clarification") else None),
            )

        case "plan_retrieval":
            queries = u.get("queries") or []
            slots = {k: v for k, v in (u.get("plan_slots") or {}).items() if v}
            return f"Lập kế hoạch: {len(queries)} truy vấn", _rows(
                _row("Câu hỏi độc lập (đã gộp ngữ cảnh)", u.get("question")),
                _row(
                    "Truy vấn",
                    [
                        f"{q['text']}"
                        + (f" · EN: {q['text_en']}" if q.get("text_en") and q["text_en"] != q["text"] else "")
                        + (f" · lọc: {', '.join(q['doc_types'])}" if q.get("doc_types") else "")
                        for q in queries
                    ],
                ),
                _row("Thông tin trích ra", [f"{k}: {v}" for k, v in slots.items()]),
            )

        case "retrieve":
            ev = u.get("evidence") or []
            docs = {e["source_path"] for e in ev}
            return f"Tìm thấy {len(ev)} đoạn từ {len(docs)} tài liệu", _rows(
                _row("Các đoạn tìm được (xếp theo độ liên quan)", [_source(e) for e in ev]),
                _row("Độ tương đồng cao nhất (cosine)", f"{u['max_cosine']:.2f}" if "max_cosine" in u else None),
                _row("Lần tìm", u.get("retrieval_attempts")),
            )

        case "grade_evidence":
            g = u.get("grade") or {}
            kept = u.get("evidence") or []
            label = f"Bằng chứng: {GRADE.get(g.get('status', ''), '?')}"
            label += f" · giữ {len(kept)} đoạn" if kept else ""
            label += " · tìm lại" if u.get("queries") else ""
            return label, _rows(
                _row("Kết luận", GRADE.get(g.get("status", ""), g.get("status"))),
                _row("Đoạn được giữ (đánh số lại)", [_source(e) for e in kept]),
                _row("Khía cạnh đã có nguồn", g.get("covered_aspects")),
                _row("Khía cạnh còn thiếu", g.get("missing_aspects")),
                _row("Tìm lại với truy vấn", [q["text"] for q in u.get("queries") or []]),
            )

        case "generate_answer":
            return "Đã soạn câu trả lời", _rows(_row("Bản nháp (trước kiểm tra)", u.get("draft_md"), md=True))

        case "generate_artifact":
            a = u.get("artifact") or {}
            return f"Đã soạn {a.get('title') or 'artifact'}", _artifact_rows(a)

        case "verify":
            v = u.get("verification") or {}
            issues = v.get("issues") or []
            label = (
                "Kiểm tra compliance & trích dẫn: đạt" if v.get("passed") else f"Kiểm tra: {len(issues)} vấn đề cần sửa"
            )
            return label, _rows(
                _row("Kết quả", "đạt" if v.get("passed") else "không đạt — sẽ viết lại hoặc đánh dấu cần review"),
                _row(
                    "Lớp kiểm tra",
                    "rules (regex, câu bắt buộc, trần giảm giá) + LLM verifier"
                    if v.get("llm_checked", True)
                    else "chỉ rules — LLM verifier lỗi",
                ),
                _row(
                    "Vấn đề",
                    [_issue(i) for i in issues],
                ),
            )

        case "revise":
            n = u.get("revision_count", "?")
            rows = (
                _artifact_rows(u["artifact"])
                if u.get("artifact")
                else _rows(_row("Bản nháp mới", u.get("draft_md"), md=True))
            )
            return f"Đã viết lại bản nháp (lần {n})", rows

        case "abstain":
            note = u.get("abstain") or {}
            found = [f"{c.get('text')} [{', '.join(c.get('source_ids') or [])}]" for c in note.get("found") or []]
            return "Không đủ thông tin — đã tóm tắt phần còn thiếu", _rows(
                _row("Đã tìm thấy trong KB", found),
                _row("Còn thiếu", note.get("missing")),
                _row("Gợi ý", note.get("suggestion")),
            )

        case "respond_direct":
            kind = "cần hỏi lại" if u.get("outcome") == "clarification" else "ngoài phạm vi KB"
            return f"Trả lời trực tiếp ({kind})", _rows(_row("Trả lời", u.get("draft_md"), md=True))

        case "finalize":
            f = u.get("final") or {}
            comp = f.get("compliance") or {}
            return f"Hoàn tất: {STATUS.get(f.get('status', ''), f.get('status', ''))}", _rows(
                _row("Trạng thái", STATUS.get(f.get("status", ""), f.get("status"))),
                _row("Độ tin cậy (tính theo luật, không hỏi LLM)", f.get("confidence")),
                _row("Số trích dẫn", len(f.get("citations") or [])),
                _row(
                    "Compliance",
                    ("đạt" if comp.get("passed", True) else "cần review")
                    + (f" · {len(comp.get('warnings') or [])} cảnh báo" if comp.get("warnings") else ""),
                ),
            )
    return node, []


def _issue(i: dict[str, Any]) -> str:
    rule = i.get("rule_id") or i.get("kind")
    return f"[{i.get('severity')}] {rule}: “{i.get('excerpt')}” → {i.get('fix_hint')}"


def _artifact_rows(a: dict[str, Any]) -> Detail:
    notes = a.get("compliance_notes") or []
    return _rows(
        _row("Tiêu đề", a.get("title")),
        _row("Các mục", [k for k, v in a.items() if v and k not in {"title", "compliance_notes", "open_questions"}]),
        _row(
            "Claim bị từ chối (compliance)",
            [f"{n.get('rule_id')}: “{n.get('requested_claim')}”" for n in notes],
        ),
        _row("Câu hỏi mở (KB chưa có)", a.get("open_questions")),
    )
