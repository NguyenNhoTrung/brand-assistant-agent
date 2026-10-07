"use client";

import { useQuery } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { useState } from "react";
import { api } from "@/lib/api";
import type { SourceView } from "@/lib/types.gen";
import { openSource, sourceUrl } from "./source-card";

export type CiteTarget = { label: string; chunkId: string; title: string; section?: string; effectiveDate?: string };

/** `[1]` trong câu trả lời — hover → tài liệu, section, đoạn trích, ngày hiệu lực (đọc `/v1/sources`). */
export function Citation({ target }: { target: CiteTarget }) {
  const [open, setOpen] = useState(false);
  const src = useQuery({
    queryKey: ["source", target.chunkId],
    // chunk_id chứa "/" và "#" → encode từng phần, "#" thành %23
    queryFn: () => api<SourceView>(sourceUrl(target.chunkId)),
    enabled: open,
    staleTime: Infinity,
  });
  const s = src.data;

  return (
    <span className="relative inline-block" onMouseEnter={() => setOpen(true)} onMouseLeave={() => setOpen(false)}>
      <button
        type="button"
        onClick={(e) => (e.stopPropagation(), openSource(target.chunkId))}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        className="mx-0.5 rounded bg-brand-100 px-1 align-super text-[0.7em] font-semibold leading-none text-brand-700 hover:bg-brand-500 hover:text-white"
      >
        {target.label}
      </button>
      {open && (
        <span className="absolute top-full left-1/2 z-30 mt-1.5 block w-80 -translate-x-1/2 rounded-xl border border-stone-200 bg-white p-3 text-left text-xs font-normal leading-relaxed text-stone-700 shadow-lg">
          <span className="block font-semibold text-stone-900">{s?.title ?? target.title}</span>
          <span className="block text-stone-500">
            {s?.section || target.section}
            {(s?.effective_date || target.effectiveDate) && <> · hiệu lực {s?.effective_date || target.effectiveDate}</>}
            {s && <> · v{s.version}</>}
            {s?.status === "superseded" && <span className="ml-1 text-amber-700">(đã bị thay thế)</span>}
          </span>
          {src.isLoading && <Loader2 className="mt-2 size-3 animate-spin text-stone-400" />}
          {src.isError && <span className="mt-2 block text-red-600">Không tải được nội dung nguồn.</span>}
          {s && <span className="mt-2 line-clamp-6 block whitespace-pre-line text-stone-600">{s.content}</span>}
          <span className="mt-2 block font-mono text-[10px] text-stone-400">{target.chunkId}</span>
        </span>
      )}
    </span>
  );
}
