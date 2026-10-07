import { EventSourceParserStream } from "eventsource-parser/stream";
import { toApiError } from "./api";
import { gatewayFetch } from "./gateway-fetch";
import { TERMINAL, type GatewayEvent } from "./turn";
import type { EventType } from "./types.gen";

/** Đọc SSE của job bằng fetch (cần header Authorization nên không dùng EventSource). */
export async function* streamJob(
  jobId: string,
  lastEventId?: string,
  signal?: AbortSignal,
): AsyncGenerator<GatewayEvent> {
  const res = await gatewayFetch(`/v1/jobs/${jobId}/events`, {
    headers: lastEventId ? { "Last-Event-ID": lastEventId } : {},
    signal,
  });
  if (!res.ok || !res.body) throw await toApiError(res);
  const reader = res.body.pipeThrough(new TextDecoderStream()).pipeThrough(new EventSourceParserStream()).getReader();
  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) return;
      const type = (value.event ?? "message") as EventType;
      if (type === "heartbeat") continue;
      const envelope = JSON.parse(value.data);
      yield { id: value.id || undefined, type, data: envelope.data ?? envelope };
      if (TERMINAL.has(type)) return;
    }
  } finally {
    reader.releaseLock();
  }
}
