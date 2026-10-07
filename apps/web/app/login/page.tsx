"use client";

import { Loader2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { GATEWAY_URL, gatewayFetch } from "@/lib/gateway-fetch";
import { clearAuth, saveAuth } from "@/lib/session";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("marketer@lumi.test");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    saveAuth(email, password);
    try {
      const res = await fetchMe();
      if (res.ok) {
        router.replace("/chat");
        return;
      }
      clearAuth();
      setError(res.status === 401 ? "Sai email hoặc mật khẩu" : `Gateway lỗi (${res.status})`);
    } catch {
      clearAuth();
      // fetch lỗi mạng = gateway không chạy HOẶC bị CORS chặn (origin của web không có trong CORS_ORIGINS)
      setError(`Không gọi được gateway ${GATEWAY_URL} — kiểm tra gateway đang chạy và CORS_ORIGINS có ${window.location.origin}`);
    } finally {
      setBusy(false);
    }
  }

  // Không dùng gatewayFetch trực tiếp: nó tự chuyển về /login khi 401 — ở đây muốn hiện lỗi tại chỗ
  const fetchMe = () => gatewayFetch("/auth/me", { redirectOn401: false });

  return (
    <main className="grid min-h-dvh place-items-center bg-stone-50 px-4">
      <form onSubmit={submit} className="w-full max-w-sm space-y-4 rounded-2xl border border-stone-200 bg-white p-8 shadow-sm">
        <div className="space-y-1">
          <div className="flex items-center gap-2 text-lg font-semibold text-brand-700">
            <span className="grid size-7 place-items-center rounded-md bg-brand-600 text-sm text-white">L</span>
            Lumi Brain
          </div>
          <p className="text-sm text-stone-500">Trợ lý tri thức nội bộ — sản phẩm, brand, compliance, SOP.</p>
        </div>
        <label className="block space-y-1 text-sm">
          <span className="font-medium">Email</span>
          <input
            className="w-full rounded-lg border border-stone-300 px-3 py-2 outline-none focus:border-brand-500"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            autoComplete="username"
          />
        </label>
        <label className="block space-y-1 text-sm">
          <span className="font-medium">Mật khẩu</span>
          <input
            type="password"
            className="w-full rounded-lg border border-stone-300 px-3 py-2 outline-none focus:border-brand-500"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
            autoFocus
          />
        </label>
        {error && <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
        <button
          disabled={busy || !password}
          className="flex w-full items-center justify-center gap-2 rounded-lg bg-brand-600 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50"
        >
          {busy && <Loader2 className="size-4 animate-spin" />} Đăng nhập
        </button>
        <p className="text-xs text-stone-400">
          Tài khoản demo: <code>marketer@lumi.test</code> · <code>admin@lumi.test</code> — mật khẩu là{" "}
          <code>DEMO_*_PASSWORD</code> trong <code>.env</code>.
        </p>
      </form>
    </main>
  );
}
