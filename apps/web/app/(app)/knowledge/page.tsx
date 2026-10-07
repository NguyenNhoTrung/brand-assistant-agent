"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, RefreshCw } from "lucide-react";
import { useState } from "react";
import { api, post } from "@/lib/api";
import { streamJob } from "@/lib/events";
import { useMe } from "@/lib/queries";
import type { JobCreated, KbEntry } from "@/lib/types.gen";

export default function KnowledgePage() {
  const me = useMe();
  const qc = useQueryClient();
  const kb = useQuery({ queryKey: ["kb"], queryFn: () => api<KbEntry[]>("/admin/kb"), enabled: me.data?.role === "admin" });
  const [progress, setProgress] = useState<{ done: number; total: number; last: string } | null>(null);
  const [result, setResult] = useState<string | null>(null);

  async function reingest() {
    setResult(null);
    setProgress({ done: 0, total: 0, last: "Đang chờ worker…" });
    try {
      const job = await post<JobCreated>("/admin/ingest", { recreate: false });
      for await (const ev of streamJob(job.job_id)) {
        const d = ev.data as Record<string, unknown>;
        if (ev.type === "ingest.progress") setProgress({ done: Number(d.done), total: Number(d.total), last: `${d.source_path} — ${d.action}` });
        else if (ev.type === "message.completed") setResult(String(d.answer_md));
        else if (ev.type === "job.failed") setResult(`Lỗi: ${d.message ?? d.code}`);
      }
    } catch (e) {
      setResult(`Lỗi: ${e instanceof Error ? e.message : e}`);
    } finally {
      setProgress(null);
      void qc.invalidateQueries({ queryKey: ["kb"] });
    }
  }

  if (me.data && me.data.role !== "admin") return <p className="p-8 text-sm text-stone-500">Chỉ admin xem được trang này.</p>;

  return (
    <div className="mx-auto max-w-5xl p-6">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">Knowledge base</h1>
          <p className="text-sm text-stone-500">Tài liệu đã ingest vào Qdrant (`kb:manifest`). Tài liệu bị thay thế không được dùng để trả lời.</p>
        </div>
        <button
          onClick={() => void reingest()}
          disabled={!!progress}
          className="flex items-center gap-1.5 rounded-lg bg-brand-600 px-3 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50"
        >
          {progress ? <Loader2 className="size-4 animate-spin" /> : <RefreshCw className="size-4" />} Ingest lại
        </button>
      </div>
      {progress && (
        <div className="mb-4 rounded-lg bg-brand-50 p-3 text-sm text-brand-700">
          {progress.total > 0 ? `${progress.done}/${progress.total} · ` : ""}
          {progress.last}
          {progress.total > 0 && (
            <div className="mt-2 h-1.5 rounded bg-brand-100">
              <div className="h-1.5 rounded bg-brand-600 transition-all" style={{ width: `${(100 * progress.done) / progress.total}%` }} />
            </div>
          )}
        </div>
      )}
      {result && <p className="mb-4 rounded-lg bg-stone-100 p-3 text-sm">{result}</p>}
      {kb.isLoading && <Loader2 className="size-5 animate-spin text-stone-400" />}
      {kb.data && (
        <div className="overflow-hidden rounded-xl border border-stone-200 bg-white">
          <table className="w-full text-sm">
            <thead className="bg-stone-50 text-left text-xs uppercase text-stone-500">
              <tr>
                <th className="px-3 py-2">Tài liệu</th>
                <th className="px-3 py-2">Loại</th>
                <th className="px-3 py-2">Trạng thái</th>
                <th className="px-3 py-2">Phiên bản</th>
                <th className="px-3 py-2">Hiệu lực</th>
                <th className="px-3 py-2 text-right">Chunk</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-stone-100">
              {kb.data.map((e) => (
                <tr key={e.source_path}>
                  <td className="px-3 py-2">
                    <p className="font-medium">{e.title}</p>
                    <p className="font-mono text-xs text-stone-400">{e.source_path}</p>
                  </td>
                  <td className="px-3 py-2 text-stone-600">{e.doc_type}</td>
                  <td className="px-3 py-2">
                    <span className={`rounded-full px-2 py-0.5 text-xs ${e.status === "active" ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-700"}`}>
                      {e.status}
                    </span>
                  </td>
                  <td className="px-3 py-2 text-stone-600">v{e.version}</td>
                  <td className="px-3 py-2 text-stone-600">{e.effective_date}</td>
                  <td className="px-3 py-2 text-right text-stone-600">{e.chunk_count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
