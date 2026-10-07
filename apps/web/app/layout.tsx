import type { ReactNode } from "react";
import { Providers } from "./providers";
import "./globals.css";

export const metadata = { title: "Lumi Brain", description: "Trợ lý tri thức nội bộ Lumi Botanics" };

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="vi">
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
