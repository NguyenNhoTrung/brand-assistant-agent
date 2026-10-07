import { useQuery } from "@tanstack/react-query";
import { api } from "./api";
import type { ConversationView, JobView, MessageView } from "./types.gen";

export type Me = { id: string; email: string; role: "admin" | "member" };

export const useMe = () => useQuery({ queryKey: ["me"], queryFn: () => api<Me>("/auth/me"), staleTime: Infinity });

export const useConversations = () =>
  useQuery({ queryKey: ["conversations"], queryFn: () => api<ConversationView[]>("/v1/conversations") });

export const useMessages = (cid: string | null) =>
  useQuery({
    queryKey: ["messages", cid],
    queryFn: () => api<MessageView[]>(`/v1/conversations/${cid}/messages`),
    enabled: !!cid,
  });

export const useActiveJob = (cid: string | null) =>
  useQuery({
    queryKey: ["active-job", cid],
    queryFn: () => api<JobView | null>(`/v1/conversations/${cid}/active-job`),
    enabled: !!cid,
    staleTime: 0,
  });
