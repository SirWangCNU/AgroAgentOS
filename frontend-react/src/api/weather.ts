import { authFetch } from "./client";
import type { ApiResponse } from "../types/api";
import type { WeatherData, WeatherLocationConfig } from "../types/weather";

export async function getWeather(
  location: string = "北京"
): Promise<WeatherData> {
  const resp = await authFetch<ApiResponse<WeatherData>>(
    `/weather?location=${encodeURIComponent(location)}`
  );
  return resp.data;
}

export async function getWeatherByLocation(
  lat: number,
  lon: number
): Promise<WeatherData> {
  const resp = await authFetch<ApiResponse<WeatherData>>(
    `/weather/location?lat=${lat}&lon=${lon}`
  );
  return resp.data;
}

export async function getWeatherLocationConfig(): Promise<WeatherLocationConfig> {
  const resp = await authFetch<ApiResponse<WeatherLocationConfig>>(
    `/weather/config`
  );
  return resp.data;
}
