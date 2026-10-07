"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { SourceRef } from "@/lib/turn";
import type { Citation as CitationT } from "@/lib/types.gen";
import { Citation, type CiteTarget } from "./citation";

const CITE = /\[(S?\d+)\]/g; // [1] (bản chính thức) hoặc [S1] (bản nháp đang stream)

/**
 * Markdown KHÔNG render raw HTML (react-markdown mặc định bỏ qua HTML) — nội dung lấy từ tài liệu nên phải an toàn.
 * `[n]` → chip citation hover được.
 */
export function Markdown({ md, citations = [], sources = [] }: { md: string; citations?: CitationT[]; sources?: SourceRef[] }) {
  const resolve = (ref: string): CiteTarget | null => {
    if (ref.startsWith("S")) {
      const s = sources.find((x) => x.sid === ref);
      return s ? { label: ref, chunkId: s.chunk_id, title: s.title, section: s.section } : null;
    }
    const c = citations.find((x) => String(x.n) === ref);
    return c
      ? { label: ref, chunkId: c.chunk_id, title: c.title, section: c.section, effectiveDate: c.effective_date }
      : null;
  };

  return (
    <div className="prose prose-sm prose-stone max-w-none prose-headings:mb-2 prose-headings:mt-4 prose-p:my-2 prose-li:my-0.5">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a: ({ href, children }) => {
            if (href?.startsWith("#cite-")) {
              const target = resolve(href.slice(6));
              return target ? <Citation target={target} /> : <span>[{children}]</span>;
            }
            return (
              <a href={href} target="_blank" rel="noreferrer noopener">
                {children}
              </a>
            );
          },
        }}
      >
        {md.replace(CITE, (_, ref: string) => `[${ref}](#cite-${ref})`)}
      </ReactMarkdown>
    </div>
  );
}
