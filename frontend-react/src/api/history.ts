import { authFetch } from "./client";
import type { ApiResponse, PaginatedData } from "../types/api";

export interface HistoryRecord {
  id: string;
  source: string;
  question: string;
  answer: string;
  skill: string;
  knowledge_base_uploaded: boolean;
  ts_iso: string;
}

export async function getHistory(
  page: number = 1,
  pageSize: number = 20,
  source?: string
): Promise<PaginatedData<HistoryRecord>> {
  let url = `/history?page=${page}&page_size=${pageSize}`;
  if (source) url += `&source=${source}`;
  const resp = await authFetch<ApiResponse<PaginatedData<HistoryRecord>>>(url);
  return resp.data;
}

export async function clearHistory(): Promise<void> {
  await authFetch<ApiResponse>("/history", { method: "DELETE" });
}

export async function deleteHistoryItem(id: string): Promise<void> {
  await authFetch<ApiResponse>(`/history/${id}`, { method: "DELETE" });
}

export async function uploadHistoryToKb(id: string): Promise<void> {
  await authFetch<ApiResponse>(`/history/${id}/upload-kb`, {
    method: "POST",
  });
}
