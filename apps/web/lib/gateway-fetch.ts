import { clearAuth, getAuth } from "./session";

export const GATEWAY_URL = process.env.NEXT_PUBLIC_GATEWAY_URL ?? "http://localhost:8080";

/** Gắn Authorization vào mọi request; 401 → xóa session, về /login. */
export async function gatewayFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers);
  const auth = getAuth();
  if (auth) headers.set("Authorization", auth);
  if (init.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  const res = await fetch(GATEWAY_URL + path, { ...init, headers });
  if (res.status === 401 && typeof window !== "undefined") {
    clearAuth();
    // ngoài React component nên không có router; reload hẳn để xóa state
    // eslint-disable-next-line @next/next/no-location-assign-relative-destination
    window.location.href = "/login";
  }
  return res;
}
