import { AlertTriangle, ShieldCheck } from "lucide-react";
import type { FinalPayload } from "@/lib/types.gen";

const CONF: Record<string, string> = {
  high: "bg-emerald-50 text-emerald-700 ring-emerald-200",
  medium: "bg-amber-50 text-amber-700 ring-amber-200",
  low: "bg-red-50 text-red-700 ring-red-200",
};

const STATUS: Record<string, [string, string]> = {
  partial: ["Trả lời một phần", "bg-amber-50 text-amber-700 ring-amber-200"],
  needs_review: ["Cần review", "bg-red-50 text-red-700 ring-red-200"],
  clarification: ["Cần làm rõ", "bg-sky-50 text-sky-700 ring-sky-200"],
  out_of_scope: ["Ngoài phạm vi", "bg-stone-100 text-stone-600 ring-stone-200"],
};

const pill = "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset";

export function Badges({ final }: { final: FinalPayload }) {
  const status = STATUS[final.status];
  const warnings = final.compliance?.warnings ?? [];
  const passed = final.compliance?.passed ?? true;
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {final.confidence && <span className={`${pill} ${CONF[final.confidence]}`}>Độ tin cậy: {final.confidence}</span>}
      {status && <span className={`${pill} ${status[1]}`}>{status[0]}</span>}
      {final.status !== "abstained" && final.status !== "out_of_scope" && (
        <span
          className={`${pill} ${passed ? "bg-emerald-50 text-emerald-700 ring-emerald-200" : "bg-red-50 text-red-700 ring-red-200"}`}
          title={warnings.map((w) => `${w.rule_id ?? w.kind}: ${w.excerpt}`).join("\n")}
        >
          {passed ? <ShieldCheck className="size-3" /> : <AlertTriangle className="size-3" />}
          {passed ? "Compliance ✓" : "Compliance cần review"}
          {warnings.length > 0 && ` · ${warnings.length} cảnh báo`}
        </span>
      )}
    </div>
  );
}
