"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useEffect, useState, type ReactNode } from "react";
import { ApiError } from "@/lib/api";
import { liveJobs } from "@/lib/live-jobs";

export function Providers({ children }: { children: ReactNode }) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 10_000,
            refetchOnWindowFocus: false,
            retry: (n, e) => n < 2 && !(e instanceof ApiError && !e.retriable),
          },
        },
      }),
  );

  useEffect(() => {
    // Job kết thúc → lịch sử (message có id để feedback) + sidebar cập nhật
    liveJobs.onSettled = (turn) => {
      void client.invalidateQueries({ queryKey: ["messages", turn.conversationId] });
      void client.invalidateQueries({ queryKey: ["conversations"] });
    };
  }, [client]);

  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}
