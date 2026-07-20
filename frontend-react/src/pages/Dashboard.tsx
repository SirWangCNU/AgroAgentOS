import { Link, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  Database,
  Cpu,
  CloudSun,
  Tractor,
  BookOpen,
  Bug,
  Users,
  MessageSquare,
  Sprout,
  ArrowRight,
  TrendingUp,
  Radar,
  ShieldAlert,
  ClipboardList,
  ListTodo,
  Clock3,
} from "lucide-react";
import { useAuthStore } from "../stores/auth";
import { useHealthStore } from "../stores/health";
import { useConversationStore } from "../stores/conversation";
import { getWeather } from "../api/weather";
import StatCard from "../components/ui/StatCard";
import { getLatestInspectionRun, listFarmProposals } from "../api/farmAgent";
import { listFarmTasks } from "../api/farmTasks";
import HealthScoreCard from "../components/farm-agent/HealthScoreCard";

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
    label: "知识库管理",
    desc: "管理农业知识文档",
    path: "/workspace/knowledge",
    color: "text-accent-blue",
    bg: "bg-accent-blue/10",
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
  const { data: proposals = [] } = useQuery({
    queryKey: ["farm-agent-proposals", "dashboard"],
    queryFn: () => listFarmProposals({}),
  });
  const { data: farmTasks = [] } = useQuery({
    queryKey: ["farm-agent-tasks", "dashboard"],
    queryFn: () => listFarmTasks({}),
  });
  const { data: latestInspection = null } = useQuery({
    queryKey: ["farm-agent-latest-inspection", "dashboard"],
    queryFn: () => getLatestInspectionRun(),
  });

  const recentConversations = conversations.slice(0, 4);
  const today = new Date().toDateString();
  const todayRisks = proposals.filter((proposal) => proposal.created_at && new Date(proposal.created_at).toDateString() === today);
  const pendingProposalCount = proposals.filter((proposal) => proposal.status === "pending").length;
  const activeTaskCount = farmTasks.filter((task) => task.status === "in_progress" || task.status === "submitted").length;
  const highRiskCount = todayRisks.filter((proposal) => proposal.severity === "high" || proposal.severity === "critical").length;
  const runStatusLabel = latestInspection === null
    ? "尚未巡检"
    : {
        running: "巡检进行中",
        completed: "最近巡检完成",
        failed: "最近巡检异常",
        cancelled: "最近巡检已取消",
      }[latestInspection.status ?? "failed"];

  return (
    <div className="flex-1 overflow-auto">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-text-primary flex items-center gap-2">
            <Sprout className="w-6 h-6 text-primary" />
            数据仪表盘
          </h1>
          <p className="text-sm text-text-muted mt-1">
            查看系统运行状态、最近对话和快捷入口
          </p>
        </div>

        <section className="mb-6 overflow-hidden rounded-3xl border border-[#28503f] bg-[#173d30] p-5 text-white shadow-[0_20px_55px_-38px_rgba(15,60,43,.9)] sm:p-6">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <p className="text-[10px] font-bold uppercase tracking-[0.26em] text-[#9ac9ad]">AI farm operations</p>
              <h2 className="mt-2 text-xl font-semibold">今日农场智能决策台</h2>
              <p className="mt-1 text-sm text-[#c9ddd0]">巡检风险、人工审批和现场任务在一个闭环中协同。</p>
            </div>
            <button onClick={() => navigate("/workspace/farm-agent")} className="inline-flex items-center justify-center gap-2 rounded-xl bg-[#f5b84b] px-4 py-3 text-sm font-bold text-[#34250f] hover:bg-[#ffca69]">
              <Radar className="h-4 w-4" />开始 AI 综合巡检
            </button>
          </div>
          <div className="mt-5 grid grid-cols-2 gap-2 lg:grid-cols-4">
            {[
              { icon: ShieldAlert, label: "今日 AI 风险", value: `${todayRisks.length} 项`, sub: `${highRiskCount} 项高风险` },
              { icon: ClipboardList, label: "待确认提案", value: `${pendingProposalCount} 项`, sub: "等待人工决策" },
              { icon: ListTodo, label: "进行中任务", value: `${activeTaskCount} 项`, sub: "含待复核任务" },
              { icon: Clock3, label: "最近一次巡检", value: runStatusLabel, sub: latestInspection?.status === "running" ? "Agent 正在执行" : latestInspection?.created_at ? new Date(latestInspection.created_at).toLocaleString("zh-CN") : "可进入驾驶舱查看" },
            ].map((item) => <div key={item.label} className="rounded-2xl border border-white/10 bg-white/7 p-3.5"><item.icon className="h-4 w-4 text-[#f3c66f]" /><p className="mt-3 text-[10px] uppercase tracking-wider text-[#94b5a2]">{item.label}</p><p className="mt-1 text-base font-semibold">{item.value}</p><p className="mt-1 text-[10px] text-[#a9c1b1]">{item.sub}</p></div>)}
          </div>
        </section>

        {/* F4: 农场健康分（基于 pending 提案 + 逾期任务量化评分） */}
        <div className="mb-6">
          <HealthScoreCard proposals={proposals} tasks={farmTasks} />
        </div>

        {/* Secondary system health cards */}
        <h2 className="mb-3 text-xs font-semibold uppercase tracking-wider text-text-muted">系统运行状态</h2>
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
