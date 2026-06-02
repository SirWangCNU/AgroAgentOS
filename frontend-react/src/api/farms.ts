import { authFetch } from "./client";
import type { ApiResponse } from "../types/api";
import type { Farm, Field, TrajectoryFile, TrajectoryPoint } from "../types/farm";

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

export async function getTrajectoryAnalysis(fileId: number): Promise<{
  work_volume: Record<string, unknown>;
  work_efficiency: Record<string, unknown>;
  work_volume_chart: string;
  work_efficiency_chart: string;
}> {
  const resp = await authFetch<ApiResponse<{
    work_volume: Record<string, unknown>;
    work_efficiency: Record<string, unknown>;
    work_volume_chart: string;
    work_efficiency_chart: string;
  }>>(`/trajectories/${fileId}/analysis`);
  return resp.data;
}
