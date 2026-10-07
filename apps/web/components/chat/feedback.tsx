"use client";

import { useQueryClient } from "@tanstack/react-query";
import { ThumbsDown, ThumbsUp } from "lucide-react";
import { useState } from "react";
import { post } from "@/lib/api";
import type { Feedback as FeedbackT, MessageView } from "@/lib/types.gen";

export function Feedback({ messageId, initial }: { messageId: string; initial?: FeedbackT | null }) {
  const qc = useQueryClient();
  const [rating, setRating] = useState<1 | -1 | null>(initial?.rating ?? null);
  const [asking, setAsking] = useState(false);
  const [comment, setComment] = useState("");
  const [error, setError] = useState(false);

  async function send(r: 1 | -1, text?: string) {
    setError(false);
    const prev = rating;
    setRating(r);
    try {
      await post<MessageView>(`/v1/messages/${messageId}/feedback`, { rating: r, comment: text || null });
      setAsking(false);
      void qc.invalidateQueries({ queryKey: ["messages"] });
    } catch {
      setRating(prev);
      setError(true);
    }
  }

  const btn = (active: boolean) =>
    `rounded-md p-1 ${active ? "bg-brand-100 text-brand-700" : "text-stone-400 hover:bg-stone-100 hover:text-stone-700"}`;

  return (
    <div className="flex items-center gap-1">
      <button className={btn(rating === 1)} onClick={() => send(1)} title="Hữu ích">
        <ThumbsUp className="size-3.5" />
      </button>
      <button className={btn(rating === -1)} onClick={() => setAsking(true)} title="Chưa tốt">
        <ThumbsDown className="size-3.5" />
      </button>
      {asking && (
        <form
          className="flex items-center gap-1"
          onSubmit={(e) => {
            e.preventDefault();
            void send(-1, comment);
          }}
        >
          <input
            autoFocus
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            placeholder="Chưa tốt ở đâu? (tuỳ chọn)"
            className="w-56 rounded-md border border-stone-300 px-2 py-0.5 text-xs outline-none focus:border-brand-500"
          />
          <button className="rounded-md bg-stone-800 px-2 py-0.5 text-xs text-white">Gửi</button>
        </form>
      )}
      {rating !== null && !asking && <span className="text-xs text-stone-400">Đã ghi nhận</span>}
      {error && <span className="text-xs text-red-600">Không lưu được</span>}
    </div>
  );
}
