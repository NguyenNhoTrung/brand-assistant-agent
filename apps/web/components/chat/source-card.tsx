"use client";

import { useQuery } from "@tanstack/react-query";
import { ChevronDown, Loader2 } from "lucide-react";
import { useState } from "react";
import { api } from "@/lib/api";
import type { SourceView } from "@/lib/types.gen";
import { Markdown } from "./markdown";

export type PanelSource = { key: string; chunkId: string; label: string; title: string; section: string; meta?: string };

/** Bấm citation `[n]` trong câu trả lời → panel phải mở thẻ nguồn tương ứng. */
export const OPEN_SOURCE_EVENT = "cb:open-source";
export const openSource = (chunkId: string) =>
  window.dispatchEvent(new CustomEvent<string>(OPEN_SOURCE_EVENT, { detail: chunkId }));

export const sourceUrl = (chunkId: string) => `/v1/sources/${chunkId.split("/").map(encodeURIComponent).join("/")}`;

/** Thẻ nguồn ở panel phải — bấm để mở toàn văn đoạn trích + metadata (dùng chung cache với hover citation). */
export function SourceCard({ source, open, onToggle }: { source: PanelSource; open: boolean; onToggle: () => void }) {
  const detail = useQuery({
    queryKey: ["source", source.chunkId],
    queryFn: () => api<SourceView>(sourceUrl(source.chunkId)),
    enabled: open,
    staleTime: Infinity,
  });
  const d = detail.data;

  return (
    <li data-chunk={source.chunkId} className={`rounded-xl border text-sm transition ${open ? "border-brand-500/40 bg-brand-50/40" : "border-stone-200"}`}>
      <button onClick={onToggle} className="flex w-full gap-2 p-3 text-left" aria-expanded={open}>
        <span className="h-fit rounded bg-brand-100 px-1.5 text-xs font-semibold text-brand-700">{source.label}</span>
        <span className="min-w-0 flex-1">
          <span className="block font-medium leading-snug">{source.title}</span>
          <span className={`block text-xs text-stone-500 ${open ? "" : "truncate"}`}>{source.section}</span>
          {source.meta && <span className="block text-xs text-stone-400">{source.meta}</span>}
        </span>
        <ChevronDown className={`size-4 shrink-0 text-stone-400 transition ${open ? "rotate-180" : ""}`} />
      </button>
      {open && (
        <div className="border-t border-stone-200 px-3 pb-3 pt-2">
          {detail.isLoading && <Loader2 className="size-4 animate-spin text-stone-400" />}
          {detail.isError && <p className="text-xs text-red-600">Không tải được nội dung nguồn.</p>}
          {d && (
            <>
              <dl className="mb-2 grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 text-xs">
                <dt className="text-stone-400">Tài liệu</dt>
                <dd className="break-all font-mono text-stone-600">{d.source_path}</dd>
                <dt className="text-stone-400">Loại</dt>
                <dd className="text-stone-600">{d.doc_type}</dd>
                <dt className="text-stone-400">Hiệu lực</dt>
                <dd className="text-stone-600">
                  {d.effective_date} · v{d.version}
                  {d.status === "superseded" && <span className="ml-1 font-medium text-amber-700">· đã bị thay thế</span>}
                </dd>
              </dl>
              <div className="max-h-96 overflow-y-auto rounded-lg bg-white p-2 ring-1 ring-stone-200 [&_h1]:text-sm [&_h2]:text-sm [&_h3]:text-sm">
                <Markdown md={d.content} />
              </div>
            </>
          )}
        </div>
      )}
    </li>
  );
}
