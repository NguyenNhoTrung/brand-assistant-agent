"use client";

import { Check, Copy, Download } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import type { Citation } from "@/lib/types.gen";
import { Markdown } from "./markdown";
import { OPEN_SOURCE_EVENT, SourceCard, type PanelSource } from "./source-card";

export type { PanelSource };

type Props = { sources: PanelSource[]; citations?: Citation[]; artifactMd?: string | null; artifactTitle?: string };

export function SidePanel({ sources, citations, artifactMd, artifactTitle }: Props) {
  const [tab, setTab] = useState<"sources" | "artifact">("sources");
  const [copied, setCopied] = useState(false);
  const [openKey, setOpenKey] = useState<string | null>(null);
  const list = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const onOpen = (e: Event) => {
      const chunkId = (e as CustomEvent<string>).detail;
      setTab("sources");
      setOpenKey(chunkId);
      requestAnimationFrame(() =>
        list.current?.querySelector(`[data-chunk="${CSS.escape(chunkId)}"]`)?.scrollIntoView({ block: "nearest", behavior: "smooth" }),
      );
    };
    window.addEventListener(OPEN_SOURCE_EVENT, onOpen);
    return () => window.removeEventListener(OPEN_SOURCE_EVENT, onOpen);
  }, []);
  const active = artifactMd && tab === "artifact" ? "artifact" : artifactMd ? tab : "sources";

  async function copy() {
    await navigator.clipboard.writeText(artifactMd ?? "");
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  function download() {
    const url = URL.createObjectURL(new Blob([artifactMd ?? ""], { type: "text/markdown" }));
    const a = Object.assign(document.createElement("a"), {
      href: url,
      download: `${(artifactTitle || "artifact").replace(/[^\p{L}\p{N}]+/gu, "-").toLowerCase()}.md`,
    });
    a.click();
    URL.revokeObjectURL(url);
  }

  const tabCls = (on: boolean) =>
    `flex-1 border-b-2 py-2.5 text-sm font-medium ${on ? "border-brand-600 text-brand-700" : "border-transparent text-stone-500 hover:text-stone-800"}`;

  return (
    <aside className="flex w-[380px] shrink-0 flex-col border-l border-stone-200 bg-white">
      <div className="flex px-4">
        <button className={tabCls(active === "sources")} onClick={() => setTab("sources")}>
          Nguồn ({sources.length})
        </button>
        <button className={tabCls(active === "artifact")} onClick={() => setTab("artifact")} disabled={!artifactMd}>
          Artifact
        </button>
      </div>
      <div ref={list} className="flex-1 overflow-y-auto p-4">
        {active === "sources" ? (
          sources.length === 0 ? (
            <p className="text-sm text-stone-400">Chọn một câu trả lời để xem nguồn đã dùng.</p>
          ) : (
            <ol className="space-y-2">
              {sources.map((s) => (
                <SourceCard
                  key={`${s.key}-${s.chunkId}`}
                  source={s}
                  open={openKey === s.chunkId}
                  onToggle={() => setOpenKey(openKey === s.chunkId ? null : s.chunkId)}
                />
              ))}
            </ol>
          )
        ) : (
          <>
            <div className="mb-3 flex gap-2">
              <button onClick={copy} className="flex items-center gap-1 rounded-md px-2 py-1 text-xs ring-1 ring-stone-200 hover:bg-stone-50">
                {copied ? <Check className="size-3" /> : <Copy className="size-3" />} {copied ? "Đã copy" : "Copy Markdown"}
              </button>
              <button onClick={download} className="flex items-center gap-1 rounded-md px-2 py-1 text-xs ring-1 ring-stone-200 hover:bg-stone-50">
                <Download className="size-3" /> Tải .md
              </button>
            </div>
            <div className="[&_h1]:text-lg [&_h2]:text-base">
              <Markdown md={artifactMd ?? ""} citations={citations} />
            </div>
          </>
        )}
      </div>
    </aside>
  );
}
