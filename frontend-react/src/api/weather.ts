import { authFetch } from "./client";
import type { ApiResponse } from "../types/api";
import type { WeatherData } from "../types/weather";

export async function getWeather(
  location: string = "北京"
): Promise<WeatherData> {
  const resp = await authFetch<ApiResponse<WeatherData>>(
    `/weather?location=${encodeURIComponent(location)}`
  );
  return resp.data;
}
