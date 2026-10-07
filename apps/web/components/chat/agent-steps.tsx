"use client";

import { Check, ChevronDown, ChevronRight, Loader2 } from "lucide-react";
import { useState } from "react";
import type { Step } from "@/lib/turn";
import { Markdown } from "./markdown";

/** Các bước agent (node.started/completed). Đang chạy → luôn mở; xong → theo `defaultOpen`. Bấm từng bước → output. */
export function AgentSteps({ steps, running, defaultOpen = false }: { steps: Step[]; running: boolean; defaultOpen?: boolean }) {
  const [expanded, setExpanded] = useState(defaultOpen);
  const [allDetails, setAllDetails] = useState<boolean | null>(null); // null = mỗi bước tự quản
  if (steps.length === 0) return null;
  const open = running || expanded;
  const total = steps.reduce((ms, s) => ms + (s.durationMs ?? 0), 0);
  const hasDetails = steps.some((s) => s.detail?.length);

  return (
    <div className="mb-2 text-xs text-stone-500" onClick={(e) => e.stopPropagation()}>
      <div className="flex items-center gap-3">
        <button onClick={() => setExpanded(!expanded)} className="flex items-center gap-1 hover:text-stone-800" disabled={running}>
          {running ? <Loader2 className="size-3.5 animate-spin text-brand-600" /> : <Check className="size-3.5 text-brand-600" />}
          {running ? (steps.findLast((s) => s.status === "running")?.label ?? "Đang xử lý…") : `${steps.length} bước`}
          {!running && total > 0 && <span className="text-stone-400">· {(total / 1000).toFixed(1)}s</span>}
          {!running && <ChevronDown className={`size-3.5 transition ${open ? "rotate-180" : ""}`} />}
        </button>
        {open && hasDetails && (
          <button onClick={() => setAllDetails(!allDetails)} className="text-brand-700 hover:underline">
            {allDetails ? "Thu gọn chi tiết" : "Mở tất cả chi tiết"}
          </button>
        )}
      </div>
      {open && (
        <ol className="mt-1.5 space-y-0.5 border-l border-stone-200 pl-3">
          {steps.map((s, i) => (
            <StepRow key={`${i}-${allDetails}`} step={s} initiallyOpen={!!allDetails} />
          ))}
        </ol>
      )}
    </div>
  );
}

function StepRow({ step, initiallyOpen }: { step: Step; initiallyOpen: boolean }) {
  const [open, setOpen] = useState(initiallyOpen);
  const detail = step.detail ?? [];
  const clickable = detail.length > 0;

  return (
    <li>
      <button
        onClick={() => setOpen(!open)}
        disabled={!clickable}
        className={`flex items-center gap-1.5 rounded py-0.5 text-left ${clickable ? "hover:text-stone-900" : "cursor-default"}`}
        aria-expanded={clickable ? open : undefined}
      >
        {step.status === "running" ? (
          <Loader2 className="size-3 shrink-0 animate-spin text-brand-600" />
        ) : (
          <Check className="size-3 shrink-0 text-brand-600" />
        )}
        <span className={step.status === "running" ? "text-stone-800" : ""}>{step.label}</span>
        {step.durationMs !== undefined && <span className="text-stone-400">{(step.durationMs / 1000).toFixed(1)}s</span>}
        {clickable && <ChevronRight className={`size-3 shrink-0 text-stone-400 transition ${open ? "rotate-90" : ""}`} />}
      </button>
      {open && clickable && (
        <dl className="mb-2 ml-4 mt-1 space-y-2 rounded-lg bg-stone-50 p-3 text-stone-700 ring-1 ring-stone-200">
          {detail.map((d, i) => (
            <div key={i}>
              <dt className="mb-0.5 font-medium text-stone-500">{d.label}</dt>
              <dd>
                {Array.isArray(d.value) ? (
                  <ul className="list-disc space-y-0.5 pl-4">
                    {d.value.map((v, j) => (
                      <li key={j} className="break-words">
                        {v}
                      </li>
                    ))}
                  </ul>
                ) : d.md ? (
                  <div className="rounded-md bg-white p-2 ring-1 ring-stone-200">
                    <Markdown md={d.value} />
                  </div>
                ) : (
                  <p className="whitespace-pre-wrap break-words">{d.value}</p>
                )}
              </dd>
            </div>
          ))}
        </dl>
      )}
    </li>
  );
}
