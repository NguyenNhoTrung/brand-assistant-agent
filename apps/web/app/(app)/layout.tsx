"use client";

import { useQueryClient } from "@tanstack/react-query";
import { BookOpen, LogOut, MessageSquare, ScrollText } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useSyncExternalStore, type ReactNode } from "react";
import { Sidebar } from "@/components/sidebar";
import { liveJobs } from "@/lib/live-jobs";
import { useMe } from "@/lib/queries";
import { clearAuth, getAuth } from "@/lib/session";

const subscribeNoop = () => () => {};

export default function AppLayout({ children }: { children: ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const qc = useQueryClient();
  // sessionStorage chỉ đọc được ở client → server render coi như chưa đăng nhập, client kiểm tra lại
  const authed = useSyncExternalStore(subscribeNoop, () => !!getAuth(), () => false);
  const me = useMe();

  useEffect(() => {
    if (!getAuth()) router.replace("/login");
  }, [router]);

  function logout() {
    clearAuth();
    liveJobs.clear();
    qc.clear();
    router.replace("/login");
  }

  if (!authed) return null;
  const isAdmin = me.data?.role === "admin";
  const nav = [
    { href: "/chat", label: "Chat", icon: MessageSquare, show: true },
    { href: "/knowledge", label: "Knowledge base", icon: BookOpen, show: isAdmin },
    { href: "/admin/traces", label: "Traces", icon: ScrollText, show: isAdmin },
  ];

  return (
    <div className="flex h-dvh flex-col">
      <header className="flex h-12 shrink-0 items-center gap-6 border-b border-stone-200 bg-white px-4">
        <Link href="/chat" className="flex items-center gap-2 font-semibold text-brand-700">
          <span className="grid size-6 place-items-center rounded-md bg-brand-600 text-xs text-white">L</span>
          Lumi Brain
        </Link>
        <nav className="flex gap-1 text-sm">
          {nav
            .filter((n) => n.show)
            .map(({ href, label, icon: Icon }) => (
              <Link
                key={href}
                href={href}
                className={`flex items-center gap-1.5 rounded-md px-2.5 py-1.5 ${
                  pathname.startsWith(href) ? "bg-stone-100 text-stone-900" : "text-stone-500 hover:text-stone-900"
                }`}
              >
                <Icon className="size-4" />
                {label}
              </Link>
            ))}
        </nav>
        <div className="ml-auto flex items-center gap-3 text-sm text-stone-500">
          {me.data && (
            <span>
              {me.data.email}
              <span className="ml-1.5 rounded bg-stone-100 px-1.5 py-0.5 text-xs">{me.data.role}</span>
            </span>
          )}
          <button onClick={logout} className="flex items-center gap-1 hover:text-stone-900" title="Đăng xuất">
            <LogOut className="size-4" />
          </button>
        </div>
      </header>
      <div className="flex min-h-0 flex-1">
        {pathname.startsWith("/chat") && <Sidebar />}
        <main className="min-w-0 flex-1">{children}</main>
      </div>
    </div>
  );
}
