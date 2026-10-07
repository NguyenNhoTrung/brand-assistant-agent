"use client";

import { ArrowUp, Loader2 } from "lucide-react";
import { useState } from "react";
import type { Mode } from "@/lib/types.gen";

const ACTIONS: { mode: Mode; label: string; ready: boolean }[] = [
  { mode: "auto", label: "Tự động", ready: true },
  { mode: "qa", label: "Hỏi đáp", ready: true },
  { mode: "creative_brief", label: "Creative brief", ready: true },
  { mode: "insight_summary", label: "Insight", ready: false },
  { mode: "campaign_recommendation", label: "Campaign", ready: false },
  { mode: "compliance_review", label: "Compliance review", ready: false },
];

export function Composer({ onSend, busy }: { onSend: (text: string, mode: Mode) => Promise<boolean>; busy: boolean }) {
  const [text, setText] = useState("");
  const [mode, setMode] = useState<Mode>("auto");

  async function submit() {
    if (!text.trim() || busy) return;
    if (await onSend(text.trim(), mode)) setText("");
  }

  return (
    <div className="mx-auto w-full max-w-3xl px-4 pb-4">
      <div className="mb-2 flex flex-wrap gap-1.5">
        {ACTIONS.map((a) => (
          <button
            key={a.mode}
            disabled={!a.ready}
            title={a.ready ? undefined : "Sắp có — skill chưa được cài"}
            onClick={() => setMode(a.mode)}
            className={`rounded-full px-3 py-1 text-xs ring-1 ring-inset transition disabled:cursor-not-allowed disabled:opacity-40 ${
              mode === a.mode ? "bg-brand-600 text-white ring-brand-600" : "bg-white text-stone-600 ring-stone-200 hover:ring-stone-300"
            }`}
          >
            {a.label}
          </button>
        ))}
      </div>
      <form
        onSubmit={(e) => (e.preventDefault(), void submit())}
        className="flex items-end gap-2 rounded-2xl border border-stone-300 bg-white p-2 shadow-sm focus-within:border-brand-500"
      >
        <textarea
          rows={1}
          value={text}
          maxLength={4000}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
              e.preventDefault();
              void submit();
            }
          }}
          placeholder={mode === "creative_brief" ? "VD: Creative brief cho SPF 50 Daily Fluid trên Instagram Reels" : "Hỏi về sản phẩm, brand, compliance, SOP…"}
          className="field-sizing-content max-h-48 min-h-9 flex-1 resize-none bg-transparent px-2 py-1.5 text-sm outline-none"
        />
        <button
          disabled={busy || !text.trim()}
          className="grid size-9 shrink-0 place-items-center rounded-xl bg-brand-600 text-white hover:bg-brand-700 disabled:opacity-40"
          title="Gửi (Enter)"
        >
          {busy ? <Loader2 className="size-4 animate-spin" /> : <ArrowUp className="size-4" />}
        </button>
      </form>
    </div>
  );
}
