import { authFetch } from "./client";
import type { ApiResponse } from "../types/api";
import type { Farm, FarmInput, Field, FieldInput } from "../types/farm";
import type { FarmWeatherSummary } from "../types/weather";

export async function getFarms(): Promise<Farm[]> {
  const response = await authFetch<ApiResponse<{ farms: Farm[] }>>(
    "/farms?page=1&page_size=100"
  );
  return response.data.farms;
}

export async function getFarmDetail(farmId: number): Promise<Field[]> {
  const response = await authFetch<ApiResponse<{ fields: Field[] }>>(
    `/farms/${farmId}`
  );
  return response.data.fields;
}

export async function createFarm(data: FarmInput): Promise<void> {
  await authFetch<ApiResponse>("/farms", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateFarm(farmId: number, data: Partial<FarmInput>): Promise<void> {
  await authFetch<ApiResponse>(`/farms/${farmId}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export async function deleteFarm(farmId: number): Promise<void> {
  await authFetch<ApiResponse>(`/farms/${farmId}`, { method: "DELETE" });
}

export async function createField(farmId: number, data: FieldInput): Promise<void> {
  await authFetch<ApiResponse>(`/farms/${farmId}/fields`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateField(fieldId: number, data: Partial<FieldInput>): Promise<void> {
  await authFetch<ApiResponse>(`/fields/${fieldId}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export async function deleteField(fieldId: number): Promise<void> {
  await authFetch<ApiResponse>(`/fields/${fieldId}`, { method: "DELETE" });
}

export async function getFarmWeather(farmId: number): Promise<FarmWeatherSummary> {
  const response = await authFetch<ApiResponse<FarmWeatherSummary>>(
    `/farms/${farmId}/weather`
  );
  return response.data;
}
