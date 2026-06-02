import { authFetch } from "./client";
import type { ApiResponse } from "../types/api";

interface DocumentInfo {
  source: string;
  chunk_count: number;
}

export async function uploadDocument(
  file: File,
  adminToken: string
): Promise<{ chunks_indexed: number; bytes: number }> {
  const formData = new FormData();
  formData.append("file", file);
  const resp = await authFetch<
    ApiResponse<{ chunks_indexed: number; bytes: number }>
  >("/documents/upload", {
    method: "POST",
    body: formData,
    headers: { "X-KB-Admin-Token": adminToken },
  });
  return resp.data;
}

export async function getDocuments(): Promise<DocumentInfo[]> {
  const resp = await authFetch<ApiResponse<{ documents: DocumentInfo[] }>>(
    "/documents"
  );
  return resp.data.documents;
}

export async function deleteDocument(
  source: string,
  adminToken: string
): Promise<void> {
  await authFetch<ApiResponse>(`/documents/${encodeURIComponent(source)}`, {
    method: "DELETE",
    headers: { "X-KB-Admin-Token": adminToken },
  });
}
