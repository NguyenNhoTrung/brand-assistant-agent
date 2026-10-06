import { EventSourceParserStream } from "eventsource-parser/stream";
import { gatewayFetch } from "./gateway-fetch";
import type { EventType } from "./types.gen";

export type GatewayEvent = { id?: string; type: EventType; data: unknown };

const TERMINAL: EventType[] = ["message.completed", "job.failed", "job.cancelled"];

/** Đọc SSE của job bằng fetch (cần header Authorization nên không dùng EventSource). */
export async function* streamJob(jobId: string, lastEventId?: string, signal?: AbortSignal) {
  const res = await gatewayFetch(`/v1/jobs/${jobId}/events`, {
    headers: lastEventId ? { "Last-Event-ID": lastEventId } : {},
    signal,
  });
  if (!res.ok || !res.body) throw new Error(`SSE ${res.status}`);
  const reader = res.body
    .pipeThrough(new TextDecoderStream())
    .pipeThrough(new EventSourceParserStream())
    .getReader();
  while (true) {
    const { value, done } = await reader.read();
    if (done) return;
    const type = (value.event ?? "message") as EventType;
    if (type === "heartbeat") continue;
    const envelope = JSON.parse(value.data);
    yield { id: value.id, type, data: envelope.data ?? envelope } satisfies GatewayEvent;
    if (TERMINAL.includes(type)) return;
  }
}
