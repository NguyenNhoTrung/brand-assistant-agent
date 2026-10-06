// Header Basic lưu trong sessionStorage (mất khi đóng tab) — ARCHITECTURE_DEMO.md §15.3
const KEY = "cb.auth";

export function saveAuth(email: string, password: string): string {
  const header = "Basic " + btoa(`${email}:${password}`);
  sessionStorage.setItem(KEY, header);
  return header;
}

export function getAuth(): string | null {
  try {
    return sessionStorage.getItem(KEY);
  } catch {
    return null;
  }
}

export function clearAuth(): void {
  sessionStorage.removeItem(KEY);
}
