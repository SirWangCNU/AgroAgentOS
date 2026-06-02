import { useQuery } from "@tanstack/react-query";
import { CloudSun, Droplets, Wind, CloudRain } from "lucide-react";
import { getWeather } from "../api/weather";

export default function Weather() {
  const { data: weather, isLoading } = useQuery({
    queryKey: ["weather"],
    queryFn: () => getWeather("北京"),
    staleTime: 5 * 60 * 1000,
  });

  if (isLoading) {
    return (
      <div className="max-w-3xl mx-auto space-y-4">
        <h1 className="text-lg font-semibold flex items-center gap-2">
          <CloudSun className="w-5 h-5 text-accent-amber" /> 天气信息
        </h1>
        <div className="h-64 skeleton rounded-xl" />
      </div>
    );
  }

  if (!weather) return null;

  const { current, forecast, agriculture_advice } = weather;

  return (
    <div className="max-w-3xl mx-auto space-y-4">
      <h1 className="text-lg font-semibold flex items-center gap-2">
        <CloudSun className="w-5 h-5 text-accent-amber" /> 天气信息
      </h1>

      {/* Current */}
      <div className="bg-bg-card rounded-xl border border-border p-6">
        <div className="flex items-center justify-between">
          <div>
            <div className="text-sm text-text-muted">{current.location}</div>
            <div className="text-4xl font-bold mt-1">{current.temperature}°</div>
            <div className="text-text-secondary mt-1">{current.condition}</div>
          </div>
          <CloudSun className="w-16 h-16 text-accent-amber" />
        </div>
        <div className="grid grid-cols-3 gap-4 mt-6 pt-4 border-t border-border">
          <div className="flex items-center gap-2">
            <Droplets className="w-4 h-4 text-accent-blue" />
            <div>
              <div className="text-xs text-text-muted">湿度</div>
              <div className="text-sm font-medium">{current.humidity}%</div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Wind className="w-4 h-4 text-text-muted" />
            <div>
              <div className="text-xs text-text-muted">风力</div>
              <div className="text-sm font-medium">{current.wind_level}</div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <CloudRain className="w-4 h-4 text-accent-blue" />
            <div>
              <div className="text-xs text-text-muted">降雨概率</div>
              <div className="text-sm font-medium">{current.rain_probability}%</div>
            </div>
          </div>
        </div>
      </div>

      {/* Agriculture advice */}
      {agriculture_advice && (
        <div className="bg-bg-card rounded-xl border border-border p-4">
          <h3 className="text-sm font-medium mb-2">🌾 农事建议</h3>
          <div className="text-sm text-text-secondary whitespace-pre-line">
            {agriculture_advice}
          </div>
        </div>
      )}

      {/* Forecast */}
      {forecast?.length > 0 && (
        <div className="bg-bg-card rounded-xl border border-border p-4">
          <h3 className="text-sm font-medium mb-3">未来预报</h3>
          <div className="space-y-2">
            {forecast.map((f, i) => (
              <div
                key={i}
                className="flex items-center justify-between py-2 border-b border-border last:border-0"
              >
                <span className="text-sm text-text-secondary">{f.date}</span>
                <span className="text-sm">
                  {f.temp_min}° ~ {f.temp_max}°
                </span>
                <span className="text-xs text-accent-blue">
                  {f.rain_probability}% 雨
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
