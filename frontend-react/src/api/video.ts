import { authFetch } from "./client";
import type { ApiResponse } from "../types/api";
import type { VideoGenResponse, VideoTaskDetail, VideoTaskListResponse } from "../types/video";

export async function generateVideo(
  prompt: string,
  image?: File | null,
  model?: string
): Promise<VideoGenResponse> {
  const form = new FormData();
  form.append("prompt", prompt);
  if (model) form.append("model", model);
  if (image) form.append("image", image);
  const resp = await authFetch<ApiResponse<VideoGenResponse>>("/video/generate", {
    method: "POST",
    body: form,
  });
  return resp.data!;
}

export async function getVideoTask(taskId: string): Promise<VideoTaskDetail> {
  const resp = await authFetch<ApiResponse<VideoTaskDetail>>(`/video/tasks/${taskId}`);
  return resp.data!;
}

export async function listVideoTasks(
  page = 1,
  pageSize = 20
): Promise<VideoTaskListResponse> {
  const resp = await authFetch<ApiResponse<VideoTaskListResponse>>(
    `/video/tasks?page=${page}&page_size=${pageSize}`
  );
  return resp.data!;
}
