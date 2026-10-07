"use client";

import { Ban, FileText, Pencil, RotateCcw, SearchX, Square, TriangleAlert } from "lucide-react";
import { post } from "@/lib/api";
import type { Step, Turn } from "@/lib/turn";
import type { FinalPayload, Feedback as FeedbackT } from "@/lib/types.gen";
import { AgentSteps } from "./agent-steps";
import { Badges } from "./badges";
import { Feedback } from "./feedback";
import { Markdown } from "./markdown";

const ARTIFACT_INTENTS = new Set(["creative_brief", "insight_summary", "campaign_recommendation", "compliance_review"]);

type Props = {
  final?: FinalPayload;
  turn?: Turn;
  messageId?: string;
  feedback?: FeedbackT | null;
  savedSteps?: Step[]; // các bước đã lưu cùng message (mở lại hội thoại)
  latest?: boolean;
  selected: boolean;
  onSelect: () => void;
  onRetry?: () => void;
};

export function AssistantMessage(props: Props) {
  const { final, turn, messageId, feedback, savedSteps, latest, selected, onSelect, onRetry } = props;
  const running = !!turn && (turn.status === "queued" || turn.status === "streaming");
  const artifactTitle = (final?.artifact?.title as string | undefined) ?? "Artifact";

  return (
    <div
      onClick={onSelect}
      className={`rounded-2xl border bg-white px-4 py-3 shadow-sm transition ${
        selected ? "border-brand-500/40 ring-2 ring-brand-500/10" : "border-stone-200"
      }`}
    >
      <AgentSteps steps={turn?.steps.length ? turn.steps : (savedSteps ?? [])} running={running} defaultOpen={latest} />

      {final ? (
        <>
          {final.status === "abstained" ? (
            <div className="rounded-xl border border-amber-200 bg-amber-50 p-3">
              <p className="mb-1 flex items-center gap-1.5 text-sm font-semibold text-amber-800">
                <SearchX className="size-4" /> Không đủ thông tin trong knowledge base
              </p>
              <Markdown md={final.answer_md} citations={final.citations} />
            </div>
          ) : (
            <Markdown md={final.answer_md} citations={final.citations} />
          )}

          {final.status === "partial" && (final.missing_info?.length ?? 0) > 0 && (
            <div className="mt-2 rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-800">
              <b>Còn thiếu:</b> {final.missing_info!.join("; ")}
            </div>
          )}

          {final.status === "needs_review" && (
            <div className="mt-2 rounded-lg bg-red-50 px-3 py-2 text-xs text-red-800">
              <p className="mb-1 flex items-center gap-1 font-semibold">
                <TriangleAlert className="size-3.5" /> Chưa qua được kiểm tra — cần người review trước khi dùng
              </p>
              <ul className="list-disc pl-4">
                {final.compliance?.warnings?.map((w, i) => (
                  <li key={i}>
                    {w.rule_id && <b>{w.rule_id}: </b>}
                    {w.excerpt} — <i>{w.fix_hint}</i>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {final.artifact_md && (
            <button
              onClick={(e) => (e.stopPropagation(), onSelect())}
              className="mt-3 flex w-full items-center gap-2 rounded-xl border border-brand-500/30 bg-brand-50 px-3 py-2 text-left text-sm text-brand-700 hover:bg-brand-100"
            >
              <FileText className="size-4" />
              <span className="font-medium">{artifactTitle}</span>
              <span className="ml-auto text-xs">Xem ở panel bên phải →</span>
            </button>
          )}

          <div className="mt-3 flex flex-wrap items-center justify-between gap-2 border-t border-stone-100 pt-2">
            <div className="flex items-center gap-2">
              <Badges final={final} />
              {(turn?.revision ?? 0) > 0 && (
                <span className="flex items-center gap-1 text-xs text-stone-400">
                  <Pencil className="size-3" /> đã chỉnh sau kiểm tra
                </span>
              )}
            </div>
            {messageId && <Feedback messageId={messageId} initial={feedback} />}
          </div>
        </>
      ) : turn?.status === "failed" ? (
        <div className="flex items-center justify-between gap-2 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
          <span>
            Lỗi: {turn.error?.message ?? "không rõ"} <code className="text-xs">({turn.error?.code})</code>
          </span>
          {onRetry && (
            <button onClick={onRetry} className="flex items-center gap-1 rounded-md bg-white px-2 py-1 text-xs ring-1 ring-red-200">
              <RotateCcw className="size-3" /> Thử lại
            </button>
          )}
        </div>
      ) : turn?.status === "cancelled" ? (
        <p className="flex items-center gap-1.5 text-sm text-stone-500">
          <Ban className="size-4" /> Đã hủy.
        </p>
      ) : turn ? (
        <>
          {turn.draft ? (
            <Markdown md={turn.draft + " ▍"} sources={turn.sources} />
          ) : ARTIFACT_INTENTS.has(turn.intent ?? "") ? (
            <p className="text-sm text-stone-500">
              Đang soạn {turn.intent} — chỉ hiển thị sau khi qua kiểm tra compliance.
            </p>
          ) : null}
          {running && (
            <button
              onClick={(e) => (e.stopPropagation(), void post(`/v1/jobs/${turn.jobId}/cancel`))}
              className="mt-2 flex items-center gap-1 rounded-md px-2 py-1 text-xs text-stone-500 ring-1 ring-stone-200 hover:bg-stone-50"
            >
              <Square className="size-3" /> Dừng
            </button>
          )}
        </>
      ) : null}
    </div>
  );
}
