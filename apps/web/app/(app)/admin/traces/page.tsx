"use client";

import { useQuery } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { api } from "@/lib/api";
import { useMe } from "@/lib/queries";

type TraceRow = { job_id: string; recorded_at: number; user_id?: string; input?: { text?: string }; scores?: Record<string, unknown> };

export default function TracesPage() {
  const me = useMe();
  const traces = useQuery({
    queryKey: ["traces"],
    queryFn: () => api<TraceRow[]>("/admin/traces"),
    enabled: me.data?.role === "admin",
  });

  if (me.data && me.data.role !== "admin") return <p className="p-8 text-sm text-stone-500">Chỉ admin xem được trang này.</p>;

  return (
    <div className="mx-auto max-w-5xl p-6">
      <h1 className="text-xl font-semibold">Traces</h1>
      <p className="mb-4 text-sm text-stone-500">Mỗi job một trace: các bước, lời gọi LLM, chi phí, điểm.</p>
      {traces.isLoading && <Loader2 className="size-5 animate-spin text-stone-400" />}
      {traces.data?.length === 0 && (
        <p className="rounded-xl border border-dashed border-stone-300 p-8 text-center text-sm text-stone-500">
          Chưa có trace — worker sẽ ghi trace khi bật <code>JobTracer</code> (Bước 9).
        </p>
      )}
      {!!traces.data?.length && (
        <ul className="divide-y divide-stone-100 rounded-xl border border-stone-200 bg-white text-sm">
          {traces.data.map((t) => (
            <li key={t.job_id} className="flex items-center gap-4 px-4 py-2">
              <span className="w-40 shrink-0 text-xs text-stone-400">{new Date(t.recorded_at).toLocaleString("vi-VN")}</span>
              <span className="flex-1 truncate">{t.input?.text ?? t.job_id}</span>
              <span className="text-xs text-stone-500">{String(t.scores?.status ?? "")}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
