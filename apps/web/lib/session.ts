// Header Basic lưu trong sessionStorage (mất khi đóng tab)
const KEY = "cb.auth";

export function saveAuth(email: string, password: string): string {
  const header = "Basic " + btoa(String.fromCharCode(...new TextEncoder().encode(`${email}:${password}`)));
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
  try {
    sessionStorage.removeItem(KEY);
  } catch {
    // sessionStorage bị chặn → không có gì để xóa
  }
}
