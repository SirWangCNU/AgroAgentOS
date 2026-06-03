import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  CloudSun,
  Droplets,
  Wind,
  CloudRain,
  Thermometer,
  Search,
  Wheat,
} from "lucide-react";
import { getWeather } from "../api/weather";
import WorkspaceLayout from "../components/layout/WorkspaceLayout";
import StatCard from "../components/ui/StatCard";
import LoadingGrid from "../components/ui/LoadingGrid";

export default function Weather() {
  const [city, setCity] = useState("北京");
  const [inputCity, setInputCity] = useState("北京");

  const { data: weather, isLoading } = useQuery({
    queryKey: ["weather", city],
    queryFn: () => getWeather(city),
    staleTime: 5 * 60 * 1000,
  });

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (inputCity.trim()) setCity(inputCity.trim());
  };

  return (
    <WorkspaceLayout
      title="天气查询"
      icon={CloudSun}
      iconColor="text-accent-amber"
      description="实时天气、农事建议与未来预报"
    >
      {/* City search */}
      <form onSubmit={handleSearch} className="mb-6">
        <div className="relative max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
          <input
            value={inputCity}
            onChange={(e) => setInputCity(e.target.value)}
            placeholder="输入城市名称..."
            className="w-full pl-9 pr-4 py-2.5 text-sm border border-border rounded-xl outline-none focus:border-primary bg-bg-card transition-colors"
          />
        </div>
      </form>

      {isLoading ? (
        <LoadingGrid rows={2} cols={3} height="h-24" />
      ) : weather ? (
        <div className="space-y-6">
          {/* Current weather hero */}
          <div className="bg-bg-card rounded-xl border border-border p-6">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-sm text-text-muted">
                  {weather.current.location}
                </div>
                <div className="text-5xl font-bold mt-2">
                  {weather.current.temperature}°
                </div>
                <div className="text-lg text-text-secondary mt-1">
                  {weather.current.condition}
                </div>
              </div>
              <CloudSun className="w-24 h-24 text-accent-amber opacity-50" />
            </div>

            {/* Detail stats */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-6 pt-5 border-t border-border">
              <StatCard
                icon={Droplets}
                label="湿度"
                value={`${weather.current.humidity}%`}
                color="text-accent-blue"
              />
              <StatCard
                icon={Wind}
                label="风力"
                value={weather.current.wind_level}
                color="text-text-secondary"
              />
              <StatCard
                icon={CloudRain}
                label="降雨概率"
                value={`${weather.current.rain_probability}%`}
                color="text-accent-blue"
              />
              <StatCard
                icon={Thermometer}
                label="体感温度"
                value={`${weather.current.temperature}°`}
                color="text-accent-amber"
              />
            </div>
          </div>

          {/* Agriculture advice */}
          {weather.agriculture_advice && (
            <div className="bg-bg-card rounded-xl border border-border p-5">
              <div className="flex items-center gap-2 mb-3">
                <Wheat className="w-5 h-5 text-accent-green" />
                <h3 className="text-sm font-semibold text-text-primary">
                  农事建议
                </h3>
              </div>
              <div className="text-sm text-text-secondary whitespace-pre-line leading-relaxed">
                {weather.agriculture_advice}
              </div>
            </div>
          )}

          {/* Forecast */}
          {weather.forecast?.length > 0 && (
            <div>
              <h3 className="text-sm font-semibold text-text-secondary mb-3">
                未来预报
              </h3>
              <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-3">
                {weather.forecast.map((f, i) => (
                  <div
                    key={i}
                    className="bg-bg-card rounded-xl border border-border p-4 text-center hover:shadow-sm transition-shadow"
                  >
                    <div className="text-xs text-text-muted font-medium">
                      {f.date}
                    </div>
                    <CloudSun className="w-8 h-8 text-accent-amber mx-auto my-2 opacity-60" />
                    <div className="text-sm font-semibold">
                      {f.temp_min}° ~ {f.temp_max}°
                    </div>
                    <div className="text-xs text-accent-blue mt-1">
                      {f.rain_probability}% 雨
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      ) : (
        <div className="text-center py-12 text-sm text-text-muted">
          无法获取天气数据，请检查城市名称
        </div>
      )}
    </WorkspaceLayout>
  );
}
