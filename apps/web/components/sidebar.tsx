"use client";

import { Loader2, Plus } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useConversations } from "@/lib/queries";
import type { ConversationView } from "@/lib/types.gen";

function groupLabel(ts: number): string {
  const day = new Date(ts).toDateString();
  if (day === new Date().toDateString()) return "Hôm nay";
  if (day === new Date(Date.now() - 86_400_000).toDateString()) return "Hôm qua";
  return "Trước đó";
}

export function Sidebar() {
  const { id } = useParams<{ id?: string[] }>();
  const current = id?.[0];
  const { data, isLoading } = useConversations();
  const groups = new Map<string, ConversationView[]>();
  for (const c of data ?? []) {
    const g = groupLabel(c.updated_at);
    groups.set(g, [...(groups.get(g) ?? []), c]);
  }

  return (
    <aside className="flex w-64 shrink-0 flex-col border-r border-stone-200 bg-white">
      <div className="p-3">
        <Link
          href="/chat"
          className="flex items-center justify-center gap-1.5 rounded-lg border border-stone-200 py-2 text-sm font-medium hover:bg-stone-50"
        >
          <Plus className="size-4" /> Hội thoại mới
        </Link>
      </div>
      <div className="flex-1 overflow-y-auto px-2 pb-3 text-sm">
        {isLoading && <Loader2 className="mx-auto mt-4 size-4 animate-spin text-stone-400" />}
        {data?.length === 0 && <p className="px-2 text-stone-400">Chưa có hội thoại nào.</p>}
        {[...groups].map(([label, convs]) => (
          <div key={label} className="mb-3">
            <p className="px-2 pb-1 text-xs font-medium text-stone-400">{label}</p>
            {convs.map((c) => (
              <Link
                key={c.id}
                href={`/chat/${c.id}`}
                className={`flex items-center gap-2 truncate rounded-md px-2 py-1.5 ${
                  c.id === current ? "bg-brand-50 text-brand-700" : "text-stone-700 hover:bg-stone-100"
                }`}
              >
                {c.active_job_id && <span className="size-1.5 shrink-0 animate-pulse rounded-full bg-brand-500" />}
                <span className="truncate">{c.title || "Không tiêu đề"}</span>
              </Link>
            ))}
          </div>
        ))}
      </div>
    </aside>
  );
}
