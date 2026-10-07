// Trạng thái MỘT lượt trả lời dựng từ event SSE (§7.2, §15.5). Hàm thuần → test bằng Vitest, không cần mạng.
import type { ComplianceIssue, EventType, FinalPayload, Mode, StepDetail } from "./types.gen";

export type GatewayEvent = { id?: string; type: EventType; data: unknown };

export type Step = { node: string; label: string; status: "running" | "done"; durationMs?: number; detail?: StepDetail[] };

export type SourceRef = { sid: string; chunk_id: string; title: string; section: string; doc_type: string };

export type Verification = { passed: boolean; issues: ComplianceIssue[]; revision: number };

export type ArtifactReady = { skill: string; content: Record<string, unknown>; rendered_md: string | null };

export type TurnStatus = "queued" | "streaming" | "done" | "failed" | "cancelled";

export type Turn = {
  jobId: string;
  conversationId: string | null;
  question: string;
  mode: Mode;
  status: TurnStatus;
  intent?: string;
  steps: Step[];
  sources: SourceRef[];
  draft: string; // token đang stream — bị thay bởi final.answer_md khi xong
  revision: number; // >0 → bản nháp đã được viết lại sau verify
  verification?: Verification;
  artifact?: ArtifactReady;
  final?: FinalPayload;
  error?: { code: string; message?: string };
  lastEventId?: string; // để resume bằng Last-Event-ID
};

export const TERMINAL: ReadonlySet<EventType> = new Set(["message.completed", "job.failed", "job.cancelled"]);

/** Nhãn hiển thị khi node chỉ có `node.completed` (load_context, finalize… không phát node.started). */
export const NODE_LABELS: Record<string, string> = {
  load_context: "Nạp ngữ cảnh hội thoại",
  route: "Phân loại yêu cầu",
  respond_direct: "Trả lời trực tiếp",
  plan_retrieval: "Lập kế hoạch tìm kiếm",
  retrieve: "Tìm trong knowledge base",
  grade_evidence: "Đánh giá bằng chứng",
  generate_answer: "Soạn câu trả lời",
  generate_artifact: "Soạn artifact",
  verify: "Kiểm tra compliance và trích dẫn",
  revise: "Viết lại bản nháp",
  abstain: "Tổng hợp phần còn thiếu",
  finalize: "Hoàn tất",
};

export function newTurn(init: Pick<Turn, "jobId" | "conversationId" | "question" | "mode">): Turn {
  return { ...init, status: "queued", steps: [], sources: [], draft: "", revision: 0 };
}

function startStep(steps: Step[], node: string, label: string): Step[] {
  return [...steps, { node, label: label || (NODE_LABELS[node] ?? node), status: "running" }];
}

/** Đóng bước đang chạy gần nhất cùng tên (node có thể chạy lại: retrieve lần 2, verify sau revise). */
function completeStep(steps: Step[], node: string, patch: Partial<Step>): Step[] {
  const i = steps.findLastIndex((s) => s.node === node && s.status === "running");
  if (i < 0) return [...steps, { node, label: NODE_LABELS[node] ?? node, ...patch, status: "done" }];
  return steps.map((s, j) => (j === i ? { ...s, ...patch, status: "done" } : s));
}

export function applyEvent(turn: Turn, ev: GatewayEvent): Turn {
  const t: Turn = ev.id ? { ...turn, lastEventId: ev.id } : { ...turn };
  const d = (ev.data ?? {}) as Record<string, unknown>;
  switch (ev.type) {
    case "job.started":
      return { ...t, status: "streaming" };
    case "node.started":
      return { ...t, steps: startStep(t.steps, String(d.node), String(d.label ?? "")) };
    case "node.completed":
      return {
        ...t,
        steps: completeStep(t.steps, String(d.node), {
          ...(d.label ? { label: String(d.label) } : {}), // nhãn KẾT QUẢ (vd. "Tìm thấy 8 đoạn…") thay nhãn "Đang…"
          ...(typeof d.duration_ms === "number" ? { durationMs: d.duration_ms } : {}),
          ...(Array.isArray(d.detail) && d.detail.length ? { detail: d.detail as StepDetail[] } : {}),
        }),
      };
    case "route.decided":
      return { ...t, intent: String(d.intent) };
    case "retrieval.sources":
      return { ...t, sources: ev.data as SourceRef[] }; // lần retrieve sau thay danh sách cũ
    case "token":
      return { ...t, status: "streaming", draft: t.draft + String(d.delta ?? "") };
    case "answer.revised":
      return { ...t, draft: "", revision: Number(d.revision ?? t.revision + 1) };
    case "verification.result":
      return { ...t, verification: ev.data as Verification };
    case "artifact.ready":
      return { ...t, artifact: ev.data as ArtifactReady };
    case "message.completed":
      return { ...t, status: "done", final: ev.data as FinalPayload, steps: t.steps.map(doneStep) };
    case "job.failed":
      return { ...t, status: "failed", error: d as Turn["error"], steps: t.steps.map(doneStep) };
    case "job.cancelled":
      return { ...t, status: "cancelled", steps: t.steps.map(doneStep) };
    default: // heartbeat, ingest.progress
      return t;
  }
}

function doneStep(s: Step): Step {
  return s.status === "running" ? { ...s, status: "done" } : s;
}
