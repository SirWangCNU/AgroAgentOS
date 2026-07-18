import type { ApiResponse } from "../types/api";
import type {
  FarmAgentEvent,
  FarmTask,
  TaskFilters,
  TaskSubmitRequest,
} from "../types/farmAgent";
import { ApiError, authFetch, authFetchRaw, consumeSSE } from "./client";
import { parseFarmAgentEvent } from "./farmAgent";

async function requireOk(response: Response): Promise<Response> {
  if (response.ok) return response;
  const message = await response.text().catch(() => "");
  throw new ApiError(response.status, message || `HTTP ${response.status}`);
}

function queryFor(filters: TaskFilters): string {
  const params = new URLSearchParams();
  if (filters.farm_id !== undefined) params.set("farm_id", String(filters.farm_id));
  if (filters.status !== undefined) params.set("status", filters.status);
  return params.size > 0 ? `?${params.toString()}` : "";
}

export async function listFarmTasks(filters: TaskFilters = {}): Promise<FarmTask[]> {
  const response = await authFetch<ApiResponse<FarmTask[]>>(
    `/farm-tasks/${queryFor(filters)}`,
  );
  return response.data;
}

export async function startFarmTask(taskId: string): Promise<FarmTask> {
  const response = await authFetch<ApiResponse<FarmTask>>(
    `/farm-tasks/${encodeURIComponent(taskId)}/start`,
    { method: "POST" },
  );
  return response.data;
}

export async function submitFarmTask(
  taskId: string,
  request: TaskSubmitRequest,
): Promise<FarmTask> {
  const response = await authFetch<ApiResponse<FarmTask>>(
    `/farm-tasks/${encodeURIComponent(taskId)}/submit`,
    { method: "POST", body: JSON.stringify(request) },
  );
  return response.data;
}

export async function* streamFarmTaskVerification(
  taskId: string,
  signal?: AbortSignal,
): AsyncGenerator<FarmAgentEvent> {
  const response = await requireOk(
    await authFetchRaw(`/farm-tasks/${encodeURIComponent(taskId)}/verify/stream`, {
      method: "POST",
      signal,
    }),
  );
  for await (const event of consumeSSE(response)) {
    yield parseFarmAgentEvent(event);
  }
}

export async function completeFarmTask(taskId: string, note: string): Promise<FarmTask> {
  const response = await authFetch<ApiResponse<FarmTask>>(
    `/farm-tasks/${encodeURIComponent(taskId)}/complete`,
    { method: "POST", body: JSON.stringify({ note }) },
  );
  return response.data;
}

export async function returnFarmTask(taskId: string, note: string): Promise<FarmTask> {
  const response = await authFetch<ApiResponse<FarmTask>>(
    `/farm-tasks/${encodeURIComponent(taskId)}/return`,
    { method: "POST", body: JSON.stringify({ note }) },
  );
  return response.data;
}
