"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { gatewayFetch } from "@/lib/gateway-fetch";
import { clearAuth, saveAuth } from "@/lib/session";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("marketer@lumi.test");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    saveAuth(email, password);
    const res = await gatewayFetch("/auth/me");
    if (res.ok) router.push("/");
    else {
      clearAuth();
      setError("Sai email hoặc mật khẩu");
    }
  }

  return (
    <main>
      <h1>Lumi Brain</h1>
      <form onSubmit={submit} style={{ display: "grid", gap: 8, maxWidth: 320 }}>
        <input value={email} onChange={(e) => setEmail(e.target.value)} placeholder="email" />
        <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="mật khẩu" />
        <button type="submit">Đăng nhập</button>
        {error && <p className="muted">{error}</p>}
        <p className="muted">Tài khoản demo: marketer@lumi.test / admin@lumi.test (mật khẩu trong .env)</p>
      </form>
    </main>
  );
}
