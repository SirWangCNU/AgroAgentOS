import { authFetch } from "./client";
import type { ApiResponse, HealthData, Skill } from "../types/api";

export async function getHealth(): Promise<HealthData> {
  const resp = await authFetch<{ data: HealthData }>("/health/ready");
  return resp.data;
}

export async function getSkills(): Promise<Skill[]> {
  const resp = await authFetch<ApiResponse<{ skills: Skill[] }>>("/skills");
  return resp.data.skills;
}
