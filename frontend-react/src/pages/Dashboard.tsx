import { Link, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  Database,
  Cpu,
  CloudSun,
  Tractor,
  BookOpen,
  Megaphone,
  Bug,
  Users,
  MessageSquare,
  Sprout,
  ArrowRight,
  TrendingUp,
} from "lucide-react";
import { useAuthStore } from "../stores/auth";
import { useHealthStore } from "../stores/health";
import { useConversationStore } from "../stores/conversation";
import { getWeather } from "../api/weather";
import StatCard from "../components/ui/StatCard";

const TOOLS = [
  {
    icon: CloudSun,
    label: "天气查询",
    desc: "实时天气与农事建议",
    path: "/workspace/weather",
    color: "text-accent-amber",
    bg: "bg-accent-amber/10",
  },
  {
    icon: Tractor,
    label: "农场管理",
    desc: "农场、地块与作业轨迹",
    path: "/workspace/farms",
    color: "text-accent-green",
    bg: "bg-accent-green/10",
  },
  {
    icon: BookOpen,
    label: "智能体技能和知识库",
    desc: "查看智能体技能与管理知识文档",
    path: "/workspace/knowledge",
    color: "text-accent-blue",
    bg: "bg-accent-blue/10",
  },
  {
    icon: Megaphone,
    label: "营销生成",
    desc: "AI 生成农产品营销文案",
    path: "/workspace/marketing",
    color: "text-accent-purple",
    bg: "bg-accent-purple/10",
  },
  {
    icon: Bug,
    label: "病虫害诊断",
    desc: "基于症状描述智能诊断",
    path: "/workspace/pest",
    color: "text-accent-red",
    bg: "bg-accent-red/10",
  },
  {
    icon: TrendingUp,
    label: "市场行情",
    desc: "价格、供需、政策补贴与销售建议",
    path: "/workspace/market",
    color: "text-accent-green",
    bg: "bg-accent-green/10",
  },
  {
    icon: MessageSquare,
    label: "智能问答",
    desc: "AI 农业助手对话",
    path: "/",
    color: "text-primary",
    bg: "bg-primary/10",
  },
];

export default function Dashboard() {
  const navigate = useNavigate();
  const isAdmin = useAuthStore((s) => s.isAdmin());
  const health = useHealthStore((s) => s.health);
  const skills = useHealthStore((s) => s.skills);
  const conversations = useConversationStore((s) => s.conversations);

  const { data: weather } = useQuery({
    queryKey: ["weather", "dashboard"],
    queryFn: () => getWeather("北京"),
    staleTime: 5 * 60 * 1000,
  });

  const recentConversations = conversations.slice(0, 4);

  return (
    <div className="flex-1 overflow-auto">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-text-primary flex items-center gap-2">
            <Sprout className="w-6 h-6 text-primary" />
            工作台
          </h1>
          <p className="text-sm text-text-muted mt-1">
            管理您的农业工具和服务
          </p>
        </div>

        {/* Status cards */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-8">
          <StatCard
            icon={Activity}
            label="系统状态"
            value={health?.status || "检查中..."}
            color="text-accent-green"
          />
          <StatCard
            icon={Database}
            label="向量数据库"
            value={health?.dependencies.milvus.status || "检查中..."}
            color="text-accent-blue"
          />
          <StatCard
            icon={Cpu}
            label="可用技能"
            value={`${skills.length} 个`}
            color="text-accent-purple"
          />
          <StatCard
            icon={CloudSun}
            label="今日天气"
            value={weather ? `${weather.current.temperature}°` : "..."}
            color="text-accent-amber"
            sub={weather?.current.condition}
          />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Tools grid — 2 cols on left */}
          <div className="lg:col-span-2">
            <h2 className="text-sm font-semibold text-text-secondary mb-3">
              功能模块
            </h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {TOOLS.map((tool) => (
                <button
                  key={tool.path}
                  onClick={() => navigate(tool.path)}
                  className="flex items-start gap-3 p-4 bg-bg-card rounded-xl border border-border hover:border-primary/40 hover:shadow-md transition-all text-left group"
                >
                  <div
                    className={`p-2.5 rounded-lg ${tool.bg} group-hover:scale-105 transition-transform`}
                  >
                    <tool.icon className={`w-5 h-5 ${tool.color}`} />
                  </div>
                  <div className="min-w-0">
                    <div className="text-sm font-semibold text-text-primary">
                      {tool.label}
                    </div>
                    <div className="text-xs text-text-muted mt-0.5">
                      {tool.desc}
                    </div>
                  </div>
                </button>
              ))}

              {isAdmin && (
                <button
                  onClick={() => navigate("/workspace/users")}
                  className="flex items-start gap-3 p-4 bg-bg-card rounded-xl border border-border hover:border-primary/40 hover:shadow-md transition-all text-left group"
                >
                  <div className="p-2.5 rounded-lg bg-accent-blue/10 group-hover:scale-105 transition-transform">
                    <Users className="w-5 h-5 text-accent-blue" />
                  </div>
                  <div className="min-w-0">
                    <div className="text-sm font-semibold text-text-primary">
                      用户管理
                    </div>
                    <div className="text-xs text-text-muted mt-0.5">
                      管理平台用户和权限
                    </div>
                  </div>
                </button>
              )}
            </div>
          </div>

          {/* Right sidebar: recent conversations */}
          <div>
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-sm font-semibold text-text-secondary">
                最近对话
              </h2>
              <button
                onClick={() => navigate("/")}
                className="text-xs text-primary hover:underline flex items-center gap-0.5"
              >
                查看全部 <ArrowRight className="w-3 h-3" />
              </button>
            </div>
            <div className="bg-bg-card rounded-xl border border-border divide-y divide-border">
              {recentConversations.length > 0 ? (
                recentConversations.map((conv) => (
                  <Link
                    key={conv.id}
                    to={`/chat/${conv.id}`}
                    className="block w-full text-left px-4 py-3 hover:bg-bg-hover transition-colors first:rounded-t-xl last:rounded-b-xl no-underline"
                  >
                    <div className="text-sm font-medium text-text-primary truncate">
                      {conv.title}
                    </div>
                    <div className="text-xs text-text-muted mt-0.5">
                      {conv.message_count} 条消息
                    </div>
                  </Link>
                ))
              ) : (
                <div className="px-4 py-8 text-center text-sm text-text-muted">
                  暂无对话记录
                </div>
              )}
            </div>

            {/* Quick weather summary */}
            {weather && (
              <div className="mt-4 bg-bg-card rounded-xl border border-border p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-xs text-text-muted">
                      {weather.current.location}
                    </div>
                    <div className="text-2xl font-bold mt-1">
                      {weather.current.temperature}°
                    </div>
                    <div className="text-sm text-text-secondary">
                      {weather.current.condition}
                    </div>
                  </div>
                  <CloudSun className="w-12 h-12 text-accent-amber opacity-60" />
                </div>
                <button
                  onClick={() => navigate("/workspace/weather")}
                  className="mt-3 w-full text-xs text-primary hover:underline text-center"
                >
                  查看详细天气 →
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
