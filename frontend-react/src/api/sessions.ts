import { authFetch } from "./client";
import type { ApiResponse } from "../types/api";

export interface SessionOut {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  message_count: number;
}

export interface SessionDetailOut extends SessionOut {
  messages: MessageOut[];
}

export interface MessageOut {
  id: number;
  role: string;
  content: string;
  image_url?: string;
  created_at: string;
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
