import { authFetch } from "./client";
import type { ApiResponse } from "../types/api";
import type { Farm, Field, TrajectoryFile, TrajectoryPoint, TrajectoryAnalysis } from "../types/farm";

// ---- Farms ----
export async function getFarms(): Promise<Farm[]> {
  const resp = await authFetch<ApiResponse<{ farms: Farm[] }>>(
    "/farms?page=1&page_size=100"
  );
  return resp.data.farms;
}

export async function getFarmDetail(farmId: number): Promise<Field[]> {
  const resp = await authFetch<ApiResponse<{ fields: Field[] }>>(
    `/farms/${farmId}`
  );
  return resp.data.fields;
}

export async function createFarm(
  data: Omit<Farm, "id" | "fields">
): Promise<void> {
  await authFetch<ApiResponse>("/farms", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateFarm(
  farmId: number,
  data: Partial<Farm>
): Promise<void> {
  await authFetch<ApiResponse>(`/farms/${farmId}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export async function deleteFarm(farmId: number): Promise<void> {
  await authFetch<ApiResponse>(`/farms/${farmId}`, { method: "DELETE" });
}

// ---- Fields ----
export async function createField(
  farmId: number,
  data: Omit<Field, "id" | "farm_id">
): Promise<void> {
  await authFetch<ApiResponse>(`/farms/${farmId}/fields`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateField(
  fieldId: number,
  data: Partial<Field>
): Promise<void> {
  await authFetch<ApiResponse>(`/fields/${fieldId}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export async function deleteField(fieldId: number): Promise<void> {
  await authFetch<ApiResponse>(`/fields/${fieldId}`, { method: "DELETE" });
}

// ---- Trajectories ----
export async function getTrajectories(
  fieldId: number
): Promise<TrajectoryFile[]> {
  const resp = await authFetch<
    ApiResponse<{ trajectories: TrajectoryFile[] }>
  >(`/fields/${fieldId}/trajectories`);
  return resp.data.trajectories;
}

export async function uploadTrajectory(
  fieldId: number,
  file: File,
  coordSystem: string
): Promise<void> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("coord_system", coordSystem);
  await authFetch<ApiResponse>(`/fields/${fieldId}/trajectories/upload`, {
    method: "POST",
    body: formData,
  });
}

export async function getTrajectoryPoints(
  fileId: number
): Promise<TrajectoryPoint[]> {
  const resp = await authFetch<ApiResponse<{ points: TrajectoryPoint[] }>>(
    `/trajectories/${fileId}/points`
  );
  return resp.data.points;
}

export async function getTrajectoryAnalysis(fileId: number): Promise<TrajectoryAnalysis> {
  const resp = await authFetch<ApiResponse<TrajectoryAnalysis>>(
    `/trajectories/${fileId}/analysis`
  );
  return resp.data;
}

export async function getTrajectoryStats(fileId: number): Promise<Record<string, unknown>> {
  const resp = await authFetch<ApiResponse<{ stats: Record<string, unknown> }>>(
    `/trajectories/${fileId}/stats`
  );
  return resp.data.stats;
}

export async function deleteTrajectory(fileId: number): Promise<void> {
  await authFetch<ApiResponse>(`/trajectories/${fileId}`, { method: "DELETE" });
}
