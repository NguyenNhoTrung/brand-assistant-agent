"use client";

// Khung chat tối thiểu. TODO(P0): AI SDK useChat + custom ChatTransport + AI Elements (§15.4).
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { streamJob } from "@/lib/events";
import { gatewayFetch } from "@/lib/gateway-fetch";
import { getAuth } from "@/lib/session";
import type { FinalPayload, JobCreated, Mode } from "@/lib/types.gen";

export default function ChatPage() {
  const router = useRouter();
  const [text, setText] = useState("");
  const [mode, setMode] = useState<Mode>("auto");
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [steps, setSteps] = useState<string[]>([]);
  const [draft, setDraft] = useState("");
  const [final, setFinal] = useState<FinalPayload | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!getAuth()) router.replace("/login");
  }, [router]);

  async function send(e: React.FormEvent) {
    e.preventDefault();
    if (!text.trim()) return;
    setBusy(true); setSteps([]); setDraft(""); setFinal(null);
    const res = await gatewayFetch("/v1/jobs", {
      method: "POST",
      headers: { "Idempotency-Key": crypto.randomUUID() },
      body: JSON.stringify({ conversation_id: conversationId, input: { text, mode } }),
    });
    const job: JobCreated = await res.json();
    setConversationId(job.conversation_id);
    try {
      for await (const ev of streamJob(job.job_id)) {
        if (ev.type === "node.completed") setSteps((s) => [...s, (ev.data as { node: string }).node]);
        else if (ev.type === "token") setDraft((d) => d + (ev.data as { delta: string }).delta);
        else if (ev.type === "message.completed") setFinal(ev.data as FinalPayload);
        else if (ev.type === "job.failed") setDraft("Lỗi: " + JSON.stringify(ev.data));
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <main>
      <h1>Lumi Brain</h1>
      <form onSubmit={send} style={{ display: "flex", gap: 8 }}>
        <select value={mode} onChange={(e) => setMode(e.target.value as Mode)}>
          {["auto", "qa", "creative_brief", "insight_summary", "campaign_recommendation", "compliance_review"].map((m) => (
            <option key={m}>{m}</option>
          ))}
        </select>
        <input style={{ flex: 1 }} value={text} onChange={(e) => setText(e.target.value)} placeholder="Hỏi về sản phẩm, brand, SOP…" />
        <button disabled={busy}>Gửi</button>
      </form>
      {steps.length > 0 && <p className="muted">✓ {steps.join(" → ")}</p>}
      {(final || draft) && (
        <div className="card">
          {final?.answer_md ?? draft}
          {final && final.citations && final.citations.length > 0 && (
            <p className="muted">
              Nguồn: {final.citations.map((c) => `[${c.n}] ${c.title}`).join(" · ")}
            </p>
          )}
        </div>
      )}
    </main>
  );
}
