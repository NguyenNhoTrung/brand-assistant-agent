import { gatewayFetch } from "./gateway-fetch";
import type { ProblemDetail } from "./types.gen";

/** Lỗi gateway dạng RFC 9457 — `code` ổn định để UI quyết định hiển thị/thử lại. */
export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly problem: Partial<ProblemDetail>,
  ) {
    super(problem.detail || problem.title || `HTTP ${status}`);
  }
  get retriable(): boolean {
    return this.status >= 500 || this.status === 0;
  }
}

export async function toApiError(res: Response): Promise<ApiError> {
  const body = await res.json().catch(() => ({}));
  return new ApiError(res.status, body as Partial<ProblemDetail>);
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await gatewayFetch(path, init);
  if (!res.ok) throw await toApiError(res);
  return (await res.json()) as T;
}

export function post<T>(path: string, body?: unknown, headers: Record<string, string> = {}): Promise<T> {
  return api<T>(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body), headers });
}
