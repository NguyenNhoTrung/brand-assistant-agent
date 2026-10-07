import { describe, expect, it } from "vitest";
import { applyEvent, newTurn, type GatewayEvent, type Turn } from "./turn";
import type { FinalPayload } from "./types.gen";

const base = () => newTurn({ jobId: "j1", conversationId: "c1", question: "Giá serum?", mode: "qa" });
const run = (events: GatewayEvent[], turn: Turn = base()) => events.reduce(applyEvent, turn);

const FINAL: FinalPayload = {
  status: "answered",
  answer_md: "Giá **$42** [1]",
  citations: [{ n: 1, sid: "S1", chunk_id: "products/serum.md#0", title: "Serum" }],
  confidence: "high",
};

describe("applyEvent — bảng §15.5", () => {
  it("job.started → streaming", () => {
    expect(run([{ type: "job.started", data: {} }]).status).toBe("streaming");
  });

  it("node.started / node.completed → bước cập nhật tại chỗ, có duration", () => {
    const t = run([
      { type: "node.started", data: { node: "route", label: "Đang phân loại" } },
      { type: "node.completed", data: { node: "route", label: "Hiểu yêu cầu: qa", duration_ms: 1200 } },
    ]);
    expect(t.steps).toEqual([{ node: "route", label: "Hiểu yêu cầu: qa", status: "done", durationMs: 1200 }]);
  });

  it("node.completed mang chi tiết output của bước", () => {
    const detail = [{ label: "Truy vấn", value: ["serum price"] }];
    const t = run([{ type: "node.completed", data: { node: "plan_retrieval", label: "Lập kế hoạch: 1 truy vấn", detail } }]);
    expect(t.steps[0].detail).toEqual(detail);
  });

  it("node.completed không có node.started → thêm bước đã xong với nhãn mặc định", () => {
    const t = run([{ type: "node.completed", data: { node: "load_context" } }]);
    expect(t.steps).toEqual([{ node: "load_context", label: "Nạp ngữ cảnh hội thoại", status: "done" }]);
  });

  it("node chạy lại (retrieve lần 2) → bước mới, không ghi đè bước cũ", () => {
    const t = run([
      { type: "node.started", data: { node: "retrieve", label: "Tìm" } },
      { type: "node.completed", data: { node: "retrieve" } },
      { type: "node.started", data: { node: "retrieve", label: "Tìm lại" } },
    ]);
    expect(t.steps.map((s) => [s.label, s.status])).toEqual([
      ["Tìm", "done"],
      ["Tìm lại", "running"],
    ]);
  });

  it("route.decided → intent", () => {
    expect(run([{ type: "route.decided", data: { intent: "creative_brief", doc_types: [] } }]).intent).toBe(
      "creative_brief",
    );
  });

  it("retrieval.sources → danh sách nguồn (lần sau thay lần trước)", () => {
    const src = (sid: string) => ({ sid, chunk_id: `x#${sid}`, title: "T", section: "", doc_type: "product" });
    const t = run([
      { type: "retrieval.sources", data: [src("S1"), src("S2")] },
      { type: "retrieval.sources", data: [src("S1")] },
    ]);
    expect(t.sources.map((s) => s.sid)).toEqual(["S1"]);
  });

  it("token → nối vào bản nháp", () => {
    const t = run([
      { type: "token", data: { delta: "Giá " } },
      { type: "token", data: { delta: "$42" } },
    ]);
    expect(t.draft).toBe("Giá $42");
  });

  it("answer.revised → xóa bản nháp, đánh dấu đã chỉnh", () => {
    const t = run([
      { type: "token", data: { delta: "cures acne" } },
      { type: "answer.revised", data: { reason: "CMP-001", revision: 1 } },
      { type: "token", data: { delta: "helps" } },
    ]);
    expect(t.draft).toBe("helps");
    expect(t.revision).toBe(1);
  });

  it("verification.result → kết quả kiểm tra", () => {
    const t = run([{ type: "verification.result", data: { passed: false, issues: [], revision: 0 } }]);
    expect(t.verification?.passed).toBe(false);
  });

  it("artifact.ready → artifact", () => {
    const t = run([{ type: "artifact.ready", data: { skill: "creative_brief", content: {}, rendered_md: "# Brief" } }]);
    expect(t.artifact?.rendered_md).toBe("# Brief");
  });

  it("message.completed → final chính thức, đóng mọi bước đang chạy", () => {
    const t = run([
      { type: "node.started", data: { node: "verify", label: "Kiểm tra" } },
      { type: "message.completed", data: FINAL },
    ]);
    expect(t.status).toBe("done");
    expect(t.final?.answer_md).toBe("Giá **$42** [1]");
    expect(t.steps.every((s) => s.status === "done")).toBe(true);
  });

  it("job.failed → lỗi có code", () => {
    const t = run([{ type: "job.failed", data: { code: "llm_unavailable", message: "x" } }]);
    expect(t.status).toBe("failed");
    expect(t.error?.code).toBe("llm_unavailable");
  });

  it("job.cancelled → cancelled", () => {
    expect(run([{ type: "job.cancelled", data: {} }]).status).toBe("cancelled");
  });

  it("ghi nhớ id event cuối để resume bằng Last-Event-ID; heartbeat không đổi gì", () => {
    const t = run([
      { id: "1-0", type: "job.started", data: {} },
      { type: "heartbeat", data: {} },
    ]);
    expect(t.lastEventId).toBe("1-0");
    expect(t.status).toBe("streaming");
  });

  it("không mutate turn đầu vào", () => {
    const t0 = base();
    applyEvent(t0, { type: "token", data: { delta: "x" } });
    expect(t0.draft).toBe("");
  });
});
