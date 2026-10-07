// SINH TỰ ĐỘNG bởi scripts/gen-types.sh từ packages/shared/contracts — KHÔNG sửa tay.

export type Text = string;
export type Mode =
  "auto" | "qa" | "creative_brief" | "insight_summary" | "campaign_recommendation" | "compliance_review";
export type ConversationId = string | null;
export type JobId = string;
export type ConversationId1 = string | null;
export type Status = "queued" | "running" | "succeeded" | "failed" | "cancelled";
export type EventsUrl = string;
export type N = number;
export type Sid = string;
export type ChunkId = string;
export type Title = string;
export type Section = string;
export type Snippet = string;
export type SourcePath = string;
export type EffectiveDate = string;
export type Kind = "unsupported_claim" | "invalid_citation" | "missing_citation" | "compliance" | "brand_voice";
export type RuleId = string | null;
export type Severity = "block" | "warn";
export type Excerpt = string;
export type FixHint = string;
export type Passed = boolean;
export type Warnings = ComplianceIssue[];
export type Status1 = "answered" | "partial" | "abstained" | "needs_review" | "clarification" | "out_of_scope";
export type AnswerMd = string;
export type Citations = Citation[];
export type Artifact = {
  [k: string]: unknown;
} | null;
export type ArtifactMd = string | null;
export type Confidence = ("high" | "medium" | "low") | null;
export type MissingInfo = string[];
export type JobId1 = string;
export type ConversationId2 = string | null;
export type UserId = string;
export type Type = "chat" | "ingest";
export type Status2 = "queued" | "running" | "succeeded" | "failed" | "cancelled";
export type Error = {
  [k: string]: unknown;
} | null;
export type CreatedAt = number;
export type StartedAt = number | null;
export type FinishedAt = number | null;
export type V = 1;
export type JobId2 = string;
export type Ts = string;
export type Data =
  | {
      [k: string]: unknown;
    }
  | unknown[];
export type Type1 = string;
export type Title1 = string;
export type Status3 = number;
export type Code =
  | "auth_required"
  | "auth_invalid"
  | "forbidden"
  | "validation_error"
  | "job_not_found"
  | "conversation_not_found"
  | "message_not_found"
  | "source_not_found"
  | "job_timeout"
  | "llm_unavailable"
  | "internal_error";
export type Detail = string | null;
export type RequestId = string | null;
export type Id = string;
export type Title2 = string;
export type UpdatedAt = number;
export type ActiveJobId = string | null;
export type Rating = 1 | -1;
export type Comment = string | null;
export type Label = string;
export type Value = string | string[];
export type Md = boolean;
export type Node = string;
export type Label1 = string;
export type DurationMs = number | null;
export type Detail1 = StepDetail[];
export type Id1 = string;
export type Role = "user" | "assistant";
export type ContentMd = string;
export type JobId3 = string;
export type CreatedAt1 = number | null;
export type Status4 = ("answered" | "partial" | "abstained" | "needs_review" | "clarification" | "out_of_scope") | null;
export type Citations1 = Citation[];
export type Confidence1 = ("high" | "medium" | "low") | null;
export type MissingInfo1 = string[];
export type Artifact1 = {
  [k: string]: unknown;
} | null;
export type ArtifactMd1 = string | null;
export type Steps = StepView[];
export type ChunkId1 = string;
export type SourcePath1 = string;
export type Title3 = string;
export type DocType = string;
export type Section1 = string;
export type Content = string;
export type EffectiveDate1 = string;
export type Version = number;
export type Status5 = string;
export type SourcePath2 = string;
export type Title4 = string;
export type DocType1 = string;
export type Status6 = string;
export type Version1 = number;
export type EffectiveDate2 = string;
export type ChunkCount = number;
export type IngestedAt = string;
export type ContentHash = string;
export type Recreate = boolean;
/**
 * This interface was referenced by `Contracts`'s JSON-Schema
 * via the `definition` "EventType".
 */
export type EventType =
  | "job.started"
  | "node.started"
  | "node.completed"
  | "route.decided"
  | "retrieval.sources"
  | "token"
  | "verification.result"
  | "answer.revised"
  | "artifact.ready"
  | "ingest.progress"
  | "message.completed"
  | "job.failed"
  | "job.cancelled"
  | "heartbeat";

export interface Contracts {
  JobInput?: JobInput;
  JobCreate?: JobCreate;
  JobCreated?: JobCreated;
  Citation?: Citation;
  ComplianceIssue?: ComplianceIssue;
  ComplianceSummary?: ComplianceSummary;
  FinalPayload?: FinalPayload;
  JobView?: JobView;
  EventEnvelope?: EventEnvelope;
  ProblemDetail?: ProblemDetail;
  ConversationView?: ConversationView;
  Feedback?: Feedback;
  StepDetail?: StepDetail;
  StepView?: StepView;
  MessageView?: MessageView;
  SourceView?: SourceView;
  KbEntry?: KbEntry;
  IngestRequest?: IngestRequest;
  EventType?: EventType;
  [k: string]: unknown;
}
/**
 * This interface was referenced by `Contracts`'s JSON-Schema
 * via the `definition` "JobInput".
 */
export interface JobInput {
  text: Text;
  mode?: Mode;
  [k: string]: unknown;
}
/**
 * This interface was referenced by `Contracts`'s JSON-Schema
 * via the `definition` "JobCreate".
 */
export interface JobCreate {
  conversation_id?: ConversationId;
  input: JobInput;
  [k: string]: unknown;
}
/**
 * This interface was referenced by `Contracts`'s JSON-Schema
 * via the `definition` "JobCreated".
 */
export interface JobCreated {
  job_id: JobId;
  conversation_id: ConversationId1;
  status: Status;
  events_url: EventsUrl;
  [k: string]: unknown;
}
/**
 * This interface was referenced by `Contracts`'s JSON-Schema
 * via the `definition` "Citation".
 */
export interface Citation {
  n: N;
  sid: Sid;
  chunk_id: ChunkId;
  title: Title;
  section?: Section;
  snippet?: Snippet;
  source_path?: SourcePath;
  effective_date?: EffectiveDate;
  [k: string]: unknown;
}
/**
 * Vấn đề verify phát hiện — `kind=compliance` kèm `rule_id`; `warn` vẫn được giao kèm cảnh báo.
 *
 * This interface was referenced by `Contracts`'s JSON-Schema
 * via the `definition` "ComplianceIssue".
 */
export interface ComplianceIssue {
  kind: Kind;
  rule_id?: RuleId;
  severity?: Severity;
  excerpt: Excerpt;
  fix_hint: FixHint;
  [k: string]: unknown;
}
/**
 * This interface was referenced by `Contracts`'s JSON-Schema
 * via the `definition` "ComplianceSummary".
 */
export interface ComplianceSummary {
  passed?: Passed;
  warnings?: Warnings;
  [k: string]: unknown;
}
/**
 * Kết quả chính thức của một lượt — `message.completed` mang payload này.
 *
 * This interface was referenced by `Contracts`'s JSON-Schema
 * via the `definition` "FinalPayload".
 */
export interface FinalPayload {
  status: Status1;
  answer_md: AnswerMd;
  citations?: Citations;
  artifact?: Artifact;
  artifact_md?: ArtifactMd;
  confidence?: Confidence;
  missing_info?: MissingInfo;
  compliance?: ComplianceSummary1;
  [k: string]: unknown;
}
export interface ComplianceSummary1 {
  passed?: Passed;
  warnings?: Warnings;
  [k: string]: unknown;
}
/**
 * This interface was referenced by `Contracts`'s JSON-Schema
 * via the `definition` "JobView".
 */
export interface JobView {
  job_id: JobId1;
  conversation_id: ConversationId2;
  user_id: UserId;
  type: Type;
  status: Status2;
  input: JobInput;
  error?: Error;
  created_at: CreatedAt;
  started_at?: StartedAt;
  finished_at?: FinishedAt;
  result?: FinalPayload | null;
  [k: string]: unknown;
}
/**
 * Field `data` của mỗi entry trong `job:{id}:events` (và của mỗi frame SSE).
 *
 * This interface was referenced by `Contracts`'s JSON-Schema
 * via the `definition` "EventEnvelope".
 */
export interface EventEnvelope {
  v?: V;
  job_id: JobId2;
  ts: Ts;
  data: Data;
  [k: string]: unknown;
}
/**
 * RFC 9457 `application/problem+json`.
 *
 * This interface was referenced by `Contracts`'s JSON-Schema
 * via the `definition` "ProblemDetail".
 */
export interface ProblemDetail {
  type?: Type1;
  title: Title1;
  status: Status3;
  code: Code;
  detail?: Detail;
  request_id?: RequestId;
  [k: string]: unknown;
}
/**
 * This interface was referenced by `Contracts`'s JSON-Schema
 * via the `definition` "ConversationView".
 */
export interface ConversationView {
  id: Id;
  title: Title2;
  updated_at: UpdatedAt;
  active_job_id?: ActiveJobId;
  [k: string]: unknown;
}
/**
 * This interface was referenced by `Contracts`'s JSON-Schema
 * via the `definition` "Feedback".
 */
export interface Feedback {
  rating: Rating;
  comment?: Comment;
  [k: string]: unknown;
}
/**
 * Một dòng output của bước agent — `value` là chuỗi hoặc danh sách; `md=True` → render Markdown.
 *
 * This interface was referenced by `Contracts`'s JSON-Schema
 * via the `definition` "StepDetail".
 */
export interface StepDetail {
  label: Label;
  value: Value;
  md?: Md;
  [k: string]: unknown;
}
/**
 * Một bước agent đã chạy (`node.completed`) — lưu cùng message assistant.
 *
 * This interface was referenced by `Contracts`'s JSON-Schema
 * via the `definition` "StepView".
 */
export interface StepView {
  node: Node;
  label?: Label1;
  duration_ms?: DurationMs;
  detail?: Detail1;
  [k: string]: unknown;
}
/**
 * `msg:{id}` — message user hoặc assistant (assistant mang thêm kết quả FinalPayload).
 *
 * This interface was referenced by `Contracts`'s JSON-Schema
 * via the `definition` "MessageView".
 */
export interface MessageView {
  id: Id1;
  role: Role;
  content_md: ContentMd;
  job_id: JobId3;
  created_at?: CreatedAt1;
  status?: Status4;
  citations?: Citations1;
  confidence?: Confidence1;
  missing_info?: MissingInfo1;
  artifact?: Artifact1;
  artifact_md?: ArtifactMd1;
  compliance?: ComplianceSummary | null;
  feedback?: Feedback | null;
  steps?: Steps;
  [k: string]: unknown;
}
/**
 * This interface was referenced by `Contracts`'s JSON-Schema
 * via the `definition` "SourceView".
 */
export interface SourceView {
  chunk_id: ChunkId1;
  source_path: SourcePath1;
  title: Title3;
  doc_type: DocType;
  section?: Section1;
  content: Content;
  effective_date: EffectiveDate1;
  version?: Version;
  status?: Status5;
  [k: string]: unknown;
}
/**
 * This interface was referenced by `Contracts`'s JSON-Schema
 * via the `definition` "KbEntry".
 */
export interface KbEntry {
  source_path: SourcePath2;
  title: Title4;
  doc_type: DocType1;
  status: Status6;
  version: Version1;
  effective_date: EffectiveDate2;
  chunk_count: ChunkCount;
  ingested_at: IngestedAt;
  content_hash: ContentHash;
  [k: string]: unknown;
}
/**
 * This interface was referenced by `Contracts`'s JSON-Schema
 * via the `definition` "IngestRequest".
 */
export interface IngestRequest {
  recreate?: Recreate;
  [k: string]: unknown;
}
