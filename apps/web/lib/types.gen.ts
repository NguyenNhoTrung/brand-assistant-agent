// SINH TỰ ĐỘNG bởi scripts/gen-types.sh từ packages/shared/contracts — KHÔNG sửa tay.

export type Text = string;
export type Mode =
  "auto" | "qa" | "creative_brief" | "insight_summary" | "campaign_recommendation" | "compliance_review";
export type ConversationId = string | null;
export type JobId = string;
export type ConversationId1 = string;
export type Status = "queued" | "running" | "succeeded" | "failed" | "cancelled";
export type EventsUrl = string;
export type JobId1 = string;
export type ConversationId2 = string;
export type UserId = string;
export type Type = "chat" | "ingest";
export type Status1 = "queued" | "running" | "succeeded" | "failed" | "cancelled";
export type Error = {
  [k: string]: unknown;
} | null;
export type CreatedAt = number;
export type StartedAt = number | null;
export type FinishedAt = number | null;
export type N = number;
export type Sid = string;
export type ChunkId = string;
export type Title = string;
export type Section = string;
export type Snippet = string;
export type Status2 = "answered" | "partial" | "abstained" | "needs_review" | "clarification" | "out_of_scope";
export type AnswerMd = string;
export type Citations = Citation[];
export type Artifact = {
  [k: string]: unknown;
} | null;
export type ArtifactMd = string | null;
export type Confidence = ("high" | "medium" | "low") | null;
export type MissingInfo = string[];
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
  | "job_timeout"
  | "llm_unavailable"
  | "internal_error";
export type Detail = string | null;
export type RequestId = string | null;
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
  | "message.completed"
  | "job.failed"
  | "job.cancelled"
  | "heartbeat";

export interface Contracts {
  JobInput?: JobInput;
  JobCreate?: JobCreate;
  JobCreated?: JobCreated;
  JobView?: JobView;
  Citation?: Citation;
  FinalPayload?: FinalPayload;
  EventEnvelope?: EventEnvelope;
  ProblemDetail?: ProblemDetail;
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
 * via the `definition` "JobView".
 */
export interface JobView {
  job_id: JobId1;
  conversation_id: ConversationId2;
  user_id: UserId;
  type: Type;
  status: Status1;
  input: JobInput;
  error?: Error;
  created_at: CreatedAt;
  started_at?: StartedAt;
  finished_at?: FinishedAt;
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
  [k: string]: unknown;
}
/**
 * Kết quả chính thức của một lượt — `message.completed` mang payload này.
 *
 * This interface was referenced by `Contracts`'s JSON-Schema
 * via the `definition` "FinalPayload".
 */
export interface FinalPayload {
  status: Status2;
  answer_md: AnswerMd;
  citations?: Citations;
  artifact?: Artifact;
  artifact_md?: ArtifactMd;
  confidence?: Confidence;
  missing_info?: MissingInfo;
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
