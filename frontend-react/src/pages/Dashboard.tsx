import { CloudSun, MessageSquare, BookOpen, Megaphone, Sprout } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { useHealthStore } from "../stores/health";
import { useQuery } from "@tanstack/react-query";
import { getWeather } from "../api/weather";

export default function Dashboard() {
  const navigate = useNavigate();
  const health = useHealthStore((s) => s.health);
  const skills = useHealthStore((s) => s.skills);

  const { data: weather } = useQuery({
    queryKey: ["weather", "dashboard"],
    queryFn: () => getWeather("北京"),
    staleTime: 5 * 60 * 1000,
  });

  return (
    <div className="max-w-6xl mx-auto space-y-4">
      <h1 className="text-lg font-semibold flex items-center gap-2">
        <Sprout className="w-5 h-5 text-primary" /> 仪表盘
      </h1>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {/* Weather Card */}
        <div className="bg-bg-card rounded-xl border border-border p-4">
          <div className="flex items-center gap-2 mb-3">
            <CloudSun className="w-5 h-5 text-accent-amber" />
            <span className="text-sm font-medium">今日天气</span>
          </div>
          {weather ? (
            <div>
              <div className="flex items-baseline gap-2">
                <span className="text-3xl font-bold">{weather.current.temperature}°</span>
                <span className="text-text-secondary">{weather.current.condition}</span>
              </div>
              <div className="text-sm text-text-muted mt-1">
                {weather.current.location} · 湿度 {weather.current.humidity}%
              </div>
            </div>
          ) : (
            <div className="h-16 skeleton" />
          )}
        </div>

        {/* Skills Card */}
        <div className="bg-bg-card rounded-xl border border-border p-4">
          <div className="flex items-center gap-2 mb-3">
            <MessageSquare className="w-5 h-5 text-primary" />
            <span className="text-sm font-medium">可用技能</span>
          </div>
          <div className="flex flex-wrap gap-2">
            {skills.map((s) => (
              <span
                key={s.name}
                className="px-2 py-1 text-xs bg-primary-light text-primary rounded-md"
              >
                {s.display_name}
              </span>
            ))}
            {!skills.length && (
              <span className="text-sm text-text-muted">加载中...</span>
            )}
          </div>
        </div>

        {/* Health Card */}
        <div className="bg-bg-card rounded-xl border border-border p-4">
          <div className="flex items-center gap-2 mb-3">
            <span className="text-sm font-medium">系统状态</span>
          </div>
          {health ? (
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-text-secondary">Milvus</span>
                <span
                  className={
                    health.dependencies.milvus.status === "ok"
                      ? "text-accent-green"
                      : "text-accent-red"
                  }
                >
                  {health.dependencies.milvus.status}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-text-secondary">MCP 工具</span>
                <span className="text-accent-green">
                  {health.dependencies.mcp.tools_count} 个
                </span>
              </div>
            </div>
          ) : (
            <div className="h-16 skeleton" />
          )}
        </div>

        {/* Quick Actions */}
        <div className="bg-bg-card rounded-xl border border-border p-4 md:col-span-2 lg:col-span-3">
          <div className="text-sm font-medium mb-3">快捷操作</div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {[
              { icon: MessageSquare, label: "智能问答", path: "/chat", color: "text-primary" },
              { icon: CloudSun, label: "天气查询", path: "/weather", color: "text-accent-amber" },
              { icon: BookOpen, label: "知识库", path: "/knowledge", color: "text-accent-blue" },
              { icon: Megaphone, label: "营销生成", path: "/marketing", color: "text-accent-purple" },
            ].map((item) => (
              <button
                key={item.path}
                onClick={() => navigate(item.path)}
                className="flex items-center gap-2 p-3 rounded-lg border border-border hover:bg-bg-hover transition-colors text-left"
              >
                <item.icon className={`w-5 h-5 ${item.color}`} />
                <span className="text-sm">{item.label}</span>
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
