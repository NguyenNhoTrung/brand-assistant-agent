// Job đang stream sống NGOÀI component: đổi URL /chat → /chat/{id} hay remount trang không làm đứt stream.
import { ApiError } from "./api";
import { streamJob } from "./events";
import { applyEvent, type Turn } from "./turn";

const MAX_RETRIES = 8;

const sleep = (ms: number, signal: AbortSignal) =>
  new Promise<void>((resolve) => {
    const t = setTimeout(resolve, ms);
    signal.addEventListener("abort", () => (clearTimeout(t), resolve()), { once: true });
  });

const isFinished = (t: Turn) => t.status === "done" || t.status === "failed" || t.status === "cancelled";

class LiveJobs {
  private turns = new Map<string, Turn>();
  private controllers = new Map<string, AbortController>();
  private listeners = new Set<() => void>();
  private version = 0;
  /** Gọi khi job kết thúc (provider gắn: invalidate query lịch sử, sidebar). */
  onSettled: (turn: Turn) => void = () => {};

  subscribe = (fn: () => void) => {
    this.listeners.add(fn);
    return () => void this.listeners.delete(fn);
  };
  getVersion = () => this.version;

  get(jobId: string): Turn | undefined {
    return this.turns.get(jobId);
  }

  forConversation(conversationId: string | null): Turn[] {
    return [...this.turns.values()].filter((t) => t.conversationId === conversationId);
  }

  /** Bắt đầu theo dõi job (bỏ qua nếu đang theo dõi). */
  follow(turn: Turn): void {
    if (this.turns.has(turn.jobId)) return;
    this.set(turn);
    const ctrl = new AbortController();
    this.controllers.set(turn.jobId, ctrl);
    void this.run(turn.jobId, ctrl.signal);
  }

  clear(): void {
    this.controllers.forEach((c) => c.abort());
    this.controllers.clear();
    this.turns.clear();
    this.bump();
  }

  private set(turn: Turn) {
    this.turns.set(turn.jobId, turn);
    this.bump();
  }

  private bump() {
    this.version++;
    this.listeners.forEach((fn) => fn());
  }

  private async run(jobId: string, signal: AbortSignal) {
    let failures = 0;
    while (!signal.aborted) {
      try {
        // Resume từ event cuối đã nhận (Last-Event-ID) → không mất / không lặp token
        for await (const ev of streamJob(jobId, this.turns.get(jobId)?.lastEventId, signal)) {
          this.set(applyEvent(this.turns.get(jobId)!, ev));
          failures = 0;
        }
        if (isFinished(this.turns.get(jobId)!)) break;
        throw new ApiError(0, { title: "Stream đóng trước khi job kết thúc" });
      } catch (e) {
        if (signal.aborted) return;
        const retriable = !(e instanceof ApiError) || e.retriable;
        if (!retriable || ++failures > MAX_RETRIES) {
          const message = e instanceof Error ? e.message : String(e);
          this.set({ ...this.turns.get(jobId)!, status: "failed", error: { code: "network", message } });
          break;
        }
        await sleep(Math.min(500 * 2 ** (failures - 1), 5000), signal);
      }
    }
    this.controllers.delete(jobId);
    if (!signal.aborted) this.onSettled(this.turns.get(jobId)!);
  }
}

export const liveJobs = new LiveJobs();
