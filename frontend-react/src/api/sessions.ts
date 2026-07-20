import { authFetch } from "./client";
import type { ApiResponse } from "../types/api";

export interface SessionOut {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  message_count: number;
}

export interface MessageOut {
  id: number;
  role: string;
  content: string;
  image_url?: string;
  status?: string; // success / error / partial
  error_message?: string | null;
  extra?: Record<string, unknown>;
  created_at: string;
}

export interface SessionDetailOut extends SessionOut {
  messages: MessageOut[];
}

export interface PaginatedMessagesOut {
  messages: MessageOut[];
  has_more: boolean;
  oldest_id: number | null;
}

export async function createSession(
  title: string = "新对话"
): Promise<SessionOut> {
  const resp = await authFetch<ApiResponse<SessionOut>>("/sessions", {
    method: "POST",
    body: JSON.stringify({ title }),
  });
  return resp.data;
}

export async function listSessions(): Promise<SessionOut[]> {
  const resp = await authFetch<ApiResponse<{ sessions: SessionOut[]; total: number }>>(
    "/sessions"
  );
  return resp.data.sessions;
}

export async function getSession(
  sessionId: string
): Promise<SessionDetailOut> {
  const resp = await authFetch<ApiResponse<SessionDetailOut>>(
    `/sessions/${sessionId}`
  );
  return resp.data;
}

export async function listMessages(
  sessionId: string,
  options?: { limit?: number; beforeId?: number | null }
): Promise<PaginatedMessagesOut> {
  const params = new URLSearchParams();
  params.set("limit", String(options?.limit ?? 10));
  if (options?.beforeId != null) {
    params.set("before_id", String(options.beforeId));
  }
  const resp = await authFetch<ApiResponse<PaginatedMessagesOut>>(
    `/sessions/${sessionId}/messages?${params}`
  );
  return resp.data;
}

export async function updateSession(
  sessionId: string,
  title: string
): Promise<void> {
  await authFetch<ApiResponse>(`/sessions/${sessionId}`, {
    method: "PUT",
    body: JSON.stringify({ title }),
  });
}

export async function deleteSession(sessionId: string): Promise<void> {
  await authFetch<ApiResponse>(`/sessions/${sessionId}`, {
    method: "DELETE",
  });
}

/**
 * 添加消息.
 *
 * 用途:
 *   - 持久化 user 消息 (前端 POST + 后端 SSE 兜底双写, 后端 5s 幂等去重)
 *   - assistant 消息已由后端 rag_service.stream_chat 主动持久化, 前端无需调用
 */
export async function addSessionMessage(
  sessionId: string,
  role: string,
  content: string,
  imageUrl?: string
): Promise<MessageOut> {
  const params = new URLSearchParams({ role, content });
  if (imageUrl) params.set("image_url", imageUrl);
  const resp = await authFetch<ApiResponse<MessageOut>>(
    `/sessions/${sessionId}/messages?${params}`,
    { method: "POST" }
  );
  return resp.data;
}