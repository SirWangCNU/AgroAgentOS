import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { MapPin, CloudSun, Loader2 } from "lucide-react";
import {
  getWeather,
  getWeatherByLocation,
  getWeatherLocationConfig,
} from "../../api/weather";
import type { WeatherData, WeatherLocationConfig } from "../../types/weather";

const REFRESH_MS = 10 * 60 * 1000;
// 浏览器 geolocation 偶尔不触发回调，额外加一层硬兜底
const LOCATION_FALLBACK_MS = 5000;

const DEFAULT_CONFIG: WeatherLocationConfig = {
  location_enabled: true,
  default_city: "北京",
  timeout_ms: 5000,
  high_accuracy: false,
};

export default function WeatherBadge() {
  const navigate = useNavigate();

  const { data: weather, isLoading } = useQuery<WeatherData>({
    queryKey: ["weather-badge"],
    queryFn: async () => {
      // 先读后端配置；若后端没重启/接口不存在，用本地默认配置兜底，绝不影响天气显示
      let config: WeatherLocationConfig;
      try {
        config = await getWeatherLocationConfig();
      } catch {
        config = DEFAULT_CONFIG;
      }

      const fetchDefault = async () => {
        try {
          return await getWeather(config.default_city || "北京");
        } catch {
          // 连默认城市也失败时返回静态兜底，避免 UI 一直转圈
          return {
            current: {
              location: config.default_city || "北京",
              temperature: 0,
              condition: "--",
              humidity: 0,
              wind_level: "-",
              rain_probability: 0,
            },
            forecast: [],
            agriculture_advice: "",
            source: "fallback",
          } as WeatherData;
        }
      };

      if (!config.location_enabled || !navigator.geolocation) {
        return fetchDefault();
      }

      return new Promise<WeatherData>((resolve) => {
        let settled = false;

        const finish = (data: WeatherData) => {
          if (settled) return;
          settled = true;
          resolve(data);
        };

        // 强制兜底：即使浏览器 geolocation 不回调，5 秒后也用默认城市
        const fallbackTimer = setTimeout(() => {
          fetchDefault().then(finish);
        }, LOCATION_FALLBACK_MS);

        navigator.geolocation.getCurrentPosition(
          (position) => {
            clearTimeout(fallbackTimer);
            getWeatherByLocation(
              position.coords.latitude,
              position.coords.longitude
            )
              .then(finish)
              .catch(() => fetchDefault().then(finish));
          },
          () => {
            clearTimeout(fallbackTimer);
            fetchDefault().then(finish);
          },
          {
            enableHighAccuracy: config.high_accuracy,
            timeout: Math.min(config.timeout_ms, LOCATION_FALLBACK_MS),
            maximumAge: REFRESH_MS,
          }
        );
      });
    },
    staleTime: REFRESH_MS,
    refetchInterval: REFRESH_MS,
  });

  return (
    <button
      onClick={() => navigate("/workspace/weather")}
      title="查看天气详情"
      className="hidden sm:flex items-center gap-1.5 px-2.5 py-1.5 text-sm rounded-lg border border-border bg-bg-card text-text-secondary hover:text-text-primary hover:border-primary transition-colors"
    >
      {isLoading || !weather ? (
        <>
          <Loader2 className="w-3.5 h-3.5 animate-spin" />
          <span className="text-xs">定位中</span>
        </>
      ) : (
        <>
          <MapPin className="w-3.5 h-3.5 text-accent-blue" />
          <span className="max-w-[6rem] truncate">
            {weather.current.location}
          </span>
          <CloudSun className="w-3.5 h-3.5 text-accent-amber" />
          <span className="font-medium">
            {weather.current.temperature}°
          </span>
        </>
      )}
    </button>
  );
}
