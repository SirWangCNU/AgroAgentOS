import { authFetch } from "./client";
import type { ApiResponse, PaginatedData } from "../types/api";

export interface HistoryRecord {
  id: number;
  source: string;
  question: string;
  answer: string;
  skill: string;
  uploaded_to_kb: boolean;
  created_at: string;
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

export async function deleteHistoryItem(id: number): Promise<void> {
  await authFetch<ApiResponse>(`/history/${id}`, { method: "DELETE" });
}

export async function uploadHistoryToKb(id: number): Promise<void> {
  await authFetch<ApiResponse>(`/history/${id}/upload-kb`, {
    method: "POST",
  });
}
