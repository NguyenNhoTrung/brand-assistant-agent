"use client";

import { useQueryClient } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import { AssistantMessage } from "@/components/chat/assistant-message";
import { Composer } from "@/components/chat/composer";
import { SidePanel, type PanelSource } from "@/components/chat/side-panel";
import { ApiError, post } from "@/lib/api";
import { liveJobs } from "@/lib/live-jobs";
import { useActiveJob, useMessages } from "@/lib/queries";
import { newTurn, type Step, type Turn } from "@/lib/turn";
import type { Feedback, FinalPayload, JobCreated, MessageView, Mode } from "@/lib/types.gen";

type Item =
  | { kind: "user"; key: string; text: string }
  | {
      kind: "assistant";
      key: string;
      jobId: string;
      final?: FinalPayload;
      turn?: Turn;
      messageId?: string;
      feedback?: Feedback | null;
      steps?: Step[];
    };

const EXAMPLES: { text: string; mode: Mode }[] = [
  { text: "How much is the Vitamin C Serum?", mode: "qa" },
  { text: "Do we ship to the EU and how long does it take?", mode: "qa" },
  { text: "What is customers' #1 pain point?", mode: "qa" },
  { text: "Creative brief for SPF 50 Daily Fluid on Instagram Reels", mode: "creative_brief" },
];

function toFinal(m: MessageView): FinalPayload {
  return {
    status: m.status ?? "answered",
    answer_md: m.content_md,
    citations: m.citations,
    artifact: m.artifact,
    artifact_md: m.artifact_md,
    confidence: m.confidence,
    missing_info: m.missing_info,
    compliance: m.compliance ?? undefined,
  };
}

const isRunning = (t: Turn) => t.status === "queued" || t.status === "streaming";

export default function ChatPage() {
  const { id } = useParams<{ id?: string[] }>();
  const cid = id?.[0] ?? null;
  const router = useRouter();
  const qc = useQueryClient();
  useSyncExternalStore(liveJobs.subscribe, liveJobs.getVersion, liveJobs.getVersion);
  const history = useMessages(cid);
  const active = useActiveJob(cid);
  const [selected, setSelected] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const [sendError, setSendError] = useState<string | null>(null);
  const sendingRef = useRef(false); // chặn double-submit trước khi state kịp render
  const idemKey = useRef<string | null>(null);
  const bottom = useRef<HTMLDivElement>(null);

  // F5 giữa lúc đang stream → tiếp tục theo dõi job đang chạy (replay từ đầu stream)
  useEffect(() => {
    const job = active.data;
    if (job && cid) {
      liveJobs.follow(newTurn({ jobId: job.job_id, conversationId: cid, question: job.input.text, mode: job.input.mode ?? "auto" }));
    }
  }, [active.data, cid]);

  const msgs = history.data ?? [];
  const saved = new Set(msgs.filter((m) => m.role === "assistant").map((m) => m.job_id));
  const pending = liveJobs.forConversation(cid).filter((t) => !saved.has(t.jobId));
  const items: Item[] = [];
  for (const m of msgs) {
    if (m.role === "user") items.push({ kind: "user", key: m.id, text: m.content_md });
    else
      items.push({
        kind: "assistant",
        key: m.id,
        jobId: m.job_id,
        final: toFinal(m),
        turn: liveJobs.get(m.job_id),
        messageId: m.id,
        feedback: m.feedback,
        steps: (m.steps ?? []).map((s) => ({
          node: s.node,
          label: s.label ?? s.node,
          status: "done" as const,
          durationMs: s.duration_ms ?? undefined,
          detail: s.detail,
        })),
      });
  }
  for (const t of pending) {
    items.push({ kind: "user", key: `q-${t.jobId}`, text: t.question });
    items.push({ kind: "assistant", key: t.jobId, jobId: t.jobId, final: t.final, turn: t });
  }

  const assistants = items.filter((i) => i.kind === "assistant");
  const current = assistants.find((i) => i.jobId === selected) ?? assistants.at(-1);
  const lastTurn = pending.at(-1);
  const scrollKey = `${items.length}:${lastTurn?.draft.length ?? 0}:${lastTurn?.steps.length ?? 0}:${lastTurn?.status}`;

  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [scrollKey]);

  async function send(text: string, mode: Mode): Promise<boolean> {
    if (sendingRef.current) return false;
    sendingRef.current = true;
    setSending(true);
    setSendError(null);
    idemKey.current ??= crypto.randomUUID(); // bấm gửi lại sau lỗi mạng → cùng key → không tạo job trùng
    try {
      const job = await post<JobCreated>(
        "/v1/jobs",
        { conversation_id: cid, input: { text, mode } },
        { "Idempotency-Key": idemKey.current },
      );
      idemKey.current = null;
      liveJobs.follow(newTurn({ jobId: job.job_id, conversationId: job.conversation_id ?? null, question: text, mode }));
      setSelected(job.job_id);
      void qc.invalidateQueries({ queryKey: ["conversations"] });
      if (!cid) router.replace(`/chat/${job.conversation_id}`);
      return true;
    } catch (e) {
      if (e instanceof ApiError && !e.retriable) idemKey.current = null;
      setSendError(e instanceof Error ? e.message : "Không gửi được");
      return false;
    } finally {
      sendingRef.current = false;
      setSending(false);
    }
  }

  const panelSources: PanelSource[] = current?.final?.citations?.length
    ? current.final.citations.map((c) => ({
        key: `${c.n}`,
        chunkId: c.chunk_id,
        label: `${c.n}`,
        title: c.title,
        section: c.section ?? "",
        meta: c.effective_date ? `Hiệu lực ${c.effective_date}` : undefined,
      }))
    : (current?.turn?.sources ?? []).map((s) => ({
        key: s.sid,
        chunkId: s.chunk_id,
        label: s.sid,
        title: s.title,
        section: s.section,
        meta: s.doc_type,
      }));
  const artifactMd = current?.final?.artifact_md ?? current?.turn?.artifact?.rendered_md;
  const artifactTitle = (current?.final?.artifact?.title as string | undefined) ?? current?.turn?.intent;

  return (
    <div className="flex h-full">
      <section className="flex min-w-0 flex-1 flex-col">
        <div className="flex-1 overflow-y-auto">
          <div className="mx-auto max-w-3xl space-y-4 px-4 py-6">
            {cid && history.isLoading && <Loader2 className="mx-auto size-5 animate-spin text-stone-400" />}
            {history.isError && <p className="text-sm text-red-600">Không tải được hội thoại.</p>}
            {!cid && items.length === 0 && (
              <div className="pt-16 text-center">
                <h1 className="text-2xl font-semibold text-stone-800">Hỏi Lumi Brain</h1>
                <p className="mt-1 text-sm text-stone-500">
                  Trả lời từ knowledge base nội bộ, kèm trích dẫn và kiểm tra compliance.
                </p>
                <div className="mx-auto mt-8 grid max-w-xl gap-2 sm:grid-cols-2">
                  {EXAMPLES.map((ex) => (
                    <button
                      key={ex.text}
                      onClick={() => void send(ex.text, ex.mode)}
                      className="rounded-xl border border-stone-200 bg-white p-3 text-left text-sm text-stone-700 hover:border-brand-500/50 hover:bg-brand-50"
                    >
                      {ex.text}
                      <span className="mt-1 block text-xs text-stone-400">{ex.mode}</span>
                    </button>
                  ))}
                </div>
              </div>
            )}
            {items.map((it) =>
              it.kind === "user" ? (
                <div key={it.key} className="flex justify-end">
                  <p className="max-w-[80%] whitespace-pre-wrap rounded-2xl rounded-br-md bg-brand-600 px-4 py-2 text-sm text-white">
                    {it.text}
                  </p>
                </div>
              ) : (
                <AssistantMessage
                  key={it.key}
                  final={it.final}
                  turn={it.turn}
                  messageId={it.messageId}
                  feedback={it.feedback}
                  savedSteps={it.steps}
                  latest={it.jobId === assistants.at(-1)?.jobId}
                  selected={it.jobId === current?.jobId && assistants.length > 1}
                  onSelect={() => setSelected(it.jobId)}
                  onRetry={it.turn ? () => void send(it.turn!.question, it.turn!.mode) : undefined}
                />
              ),
            )}
            <div ref={bottom} />
          </div>
        </div>
        {sendError && <p className="mx-auto mb-2 w-full max-w-3xl px-4 text-sm text-red-600">Không gửi được: {sendError}</p>}
        <Composer onSend={send} busy={sending || pending.some(isRunning)} />
      </section>
      <SidePanel
        sources={panelSources}
        citations={current?.final?.citations}
        artifactMd={artifactMd}
        artifactTitle={artifactTitle}
      />
    </div>
  );
}
