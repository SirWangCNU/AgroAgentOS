import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  Bot,
  CloudSun,
  Sprout,
  Bug,
  MessageSquare,
  TrendingUp,
  BookOpen,
  Radar,
  ClipboardCheck,
  Sparkles,
  Search,
  ArrowRight,
  Zap,
  LayoutDashboard,
  ShieldCheck,
  AlertTriangle,
  Tractor,
  ArrowUpRight,
} from "lucide-react";
import { useHealthStore } from "../stores/health";
import { getSkills } from "../api/health";
import type { Skill } from "../types/api";
import LoadingGrid from "../components/ui/LoadingGrid";
import EmptyState from "../components/ui/EmptyState";

const ICON_MAP: Record<string, React.ElementType> = {
  Bot,
  CloudSun,
  Sprout,
  Bug,
  MessageSquare,
  TrendingUp,
  BookOpen,
  Radar,
  ClipboardCheck,
  Sparkles,
  Tractor,
};

const RISK_COLORS: Record<string, string> = {
  low: "text-emerald-600 bg-emerald-50 border-emerald-100",
  medium: "text-amber-600 bg-amber-50 border-amber-100",
  high: "text-rose-600 bg-rose-50 border-rose-100",
};

const RISK_LABELS: Record<string, string> = {
  low: "低风险",
  medium: "中风险",
  high: "高风险",
};

interface AgentTab {
  id: string;
  label: string;
  icon: React.ElementType;
  desc: string;
  path?: string;
}

const AGENT_TABS: AgentTab[] = [
  { id: "chat", label: "智农助手", icon: MessageSquare, desc: "农业问答入口", path: "/chat" },
  { id: "farm", label: "农场驾驶舱", icon: Radar, desc: "风险巡检与任务闭环", path: "/workspace/farm-agent" },
  { id: "farms", label: "农场管理", icon: Tractor, desc: "地块与作物档案", path: "/workspace/farms" },
  { id: "dashboard", label: "数据仪表盘", icon: LayoutDashboard, desc: "全局健康分与状态", path: "/workspace/dashboard" },
];

const QUICK_CARDS = [
  {
    title: "AI 综合巡检",
    desc: "选择农场场景，注入感知数据，一键生成风险与提案",
    icon: Radar,
    path: "/workspace/farm-agent",
    bg: "from-emerald-500 to-teal-600",
  },
  {
    title: "病虫害诊断",
    desc: "上传叶片照片或描述症状，识别病害并给出防治方案",
    icon: Bug,
    path: "/workspace/pest",
    bg: "from-amber-500 to-orange-500",
  },
  {
    title: "市场行情分析",
    desc: "价格、供需、政策补贴与销售建议综合分析",
    icon: TrendingUp,
    path: "/workspace/market",
    bg: "from-blue-500 to-indigo-500",
  },
  {
    title: "天气农事建议",
    desc: "结合未来天气预报判断打药、施肥、灌溉时机",
    icon: CloudSun,
    path: "/workspace/weather",
    bg: "from-sky-400 to-cyan-500",
  },
];

export default function AgentCapabilities() {
  const navigate = useNavigate();
  const [search, setSearch] = useState("");
  const [activeTab, setActiveTab] = useState("chat");
  const storeSkills = useHealthStore((s) => s.skills);

  const { data: skills, isLoading } = useQuery<Skill[]>({
    queryKey: ["skills"],
    queryFn: getSkills,
    staleTime: 5 * 60 * 1000,
    initialData: storeSkills,
  });

  const filtered = useMemo(() => {
    const list = skills || [];
    if (!search.trim()) return list;
    const q = search.toLowerCase();
    return list.filter(
      (s) =>
        s.display_name.toLowerCase().includes(q) ||
        s.description.toLowerCase().includes(q) ||
        (s.category || "").toLowerCase().includes(q) ||
        s.triggers?.some((t) => t.toLowerCase().includes(q))
    );
  }, [skills, search]);

  const categories = useMemo(() => {
    const map = new Map<string, typeof filtered>();
    for (const s of filtered) {
      const cat = s.category || "通用";
      if (!map.has(cat)) map.set(cat, []);
      map.get(cat)!.push(s);
    }
    return Array.from(map.entries());
  }, [filtered]);

  const stats = useMemo(() => {
    const list = skills || [];
    return {
      total: list.length,
      low: list.filter((s) => s.risk_level === "low").length,
      medium: list.filter((s) => s.risk_level === "medium").length,
      high: list.filter((s) => s.risk_level === "high").length,
    };
  }, [skills]);

  const handleTry = (example: string) => {
    navigate("/chat", { state: { initialMessage: example } });
  };

  const handleTabClick = (tab: AgentTab) => {
    setActiveTab(tab.id);
    if (tab.path) navigate(tab.path);
  };

  return (
    <div className="flex flex-1 overflow-hidden relative">
      {/* 沉浸式背景 */}
      <div className="absolute inset-0 -z-10">
        <div className="absolute inset-0 bg-gradient-to-br from-[#f2f7f4] via-[#f8faf8] to-white" />
        <div className="absolute left-1/3 top-0 h-[700px] w-[700px] -translate-x-1/2 rounded-full bg-emerald-200/20 blur-[140px]" />
        <div className="absolute right-0 bottom-0 h-[500px] w-[500px] rounded-full bg-amber-200/15 blur-[120px]" />
        <div
          className="absolute inset-0 opacity-[0.25]"
          style={{
            backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 400 400' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noiseFilter'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.65' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noiseFilter)'/%3E%3C/svg%3E")`,
          }}
        />
      </div>

      <div className="mx-auto flex min-h-full w-full max-w-[1100px] flex-col overflow-y-auto px-6 py-10 sm:px-8">
        {/* Hero */}
        <div className="mb-10 text-center">
          <div className="mx-auto mb-5 flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-emerald-500 to-teal-600 text-white shadow-lg shadow-emerald-200">
            <Bot className="h-7 w-7" />
          </div>
          <h1 className="text-[34px] font-semibold leading-tight tracking-tight text-[#16271c] sm:text-[44px]">
            智能体能力中心
          </h1>
          <p className="mt-3 text-base text-slate-500 sm:text-lg">
            选择一位农业智能体，开始你的田间决策旅程
          </p>
        </div>

        {/* Agent 切换 */}
        <div className="mb-10 flex flex-wrap items-center justify-center gap-2">
          {AGENT_TABS.map((tab) => {
            const Icon = tab.icon;
            const active = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => handleTabClick(tab)}
                className={`group flex items-center gap-2.5 rounded-full border px-5 py-2.5 text-sm font-medium transition-all ${
                  active
                    ? "border-emerald-600 bg-[#16271c] text-white shadow-md"
                    : "border-slate-200 bg-white/60 text-slate-600 hover:border-emerald-300 hover:bg-white"
                }`}
              >
                <Icon className="w-4 h-4" />
                {tab.label}
                {active && <ArrowUpRight className="w-3.5 h-3.5 text-emerald-300" />}
              </button>
            );
          })}
        </div>

        {/* 推荐卡片 */}
        <div className="mb-10 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {QUICK_CARDS.map((card) => {
            const Icon = card.icon;
            return (
              <button
                key={card.title}
                onClick={() => navigate(card.path)}
                className="group relative overflow-hidden rounded-2xl bg-white p-5 text-left shadow-sm transition-all hover:-translate-y-1 hover:shadow-md"
              >
                <div
                  className={`absolute right-0 top-0 h-24 w-24 -translate-y-1/3 translate-x-1/3 rounded-full bg-gradient-to-br ${card.bg} opacity-10 blur-2xl transition-opacity group-hover:opacity-20`}
                />
                <div
                  className={`mb-4 flex h-11 w-11 items-center justify-center rounded-xl bg-gradient-to-br ${card.bg} text-white shadow-sm`}
                >
                  <Icon className="w-5 h-5" />
                </div>
                <h3 className="text-base font-semibold text-slate-800">{card.title}</h3>
                <p className="mt-1.5 text-xs leading-relaxed text-slate-500">{card.desc}</p>
                <div className="mt-4 flex items-center gap-1 text-xs font-medium text-emerald-700 opacity-0 transition-opacity group-hover:opacity-100">
                  立即体验 <ArrowRight className="w-3 h-3" />
                </div>
              </button>
            );
          })}
        </div>

        {/* 统计 */}
        <div className="mb-8 grid grid-cols-2 lg:grid-cols-4 gap-3">
          <div className="rounded-2xl border border-slate-200/60 bg-white/70 p-4 backdrop-blur-sm">
            <div className="flex items-center gap-2 text-xs text-slate-500">
              <LayoutDashboard className="w-3.5 h-3.5" />
              已注册 Skill
            </div>
            <div className="mt-2 text-2xl font-semibold text-[#16271c]">{stats.total}</div>
          </div>
          <div className="rounded-2xl border border-slate-200/60 bg-white/70 p-4 backdrop-blur-sm">
            <div className="flex items-center gap-2 text-xs text-slate-500">
              <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
              低风险
            </div>
            <div className="mt-2 text-2xl font-semibold text-[#16271c]">{stats.low}</div>
          </div>
          <div className="rounded-2xl border border-slate-200/60 bg-white/70 p-4 backdrop-blur-sm">
            <div className="flex items-center gap-2 text-xs text-slate-500">
              <Zap className="w-3.5 h-3.5 text-amber-500" />
              中风险
            </div>
            <div className="mt-2 text-2xl font-semibold text-[#16271c]">{stats.medium}</div>
          </div>
          <div className="rounded-2xl border border-slate-200/60 bg-white/70 p-4 backdrop-blur-sm">
            <div className="flex items-center gap-2 text-xs text-slate-500">
              <AlertTriangle className="w-3.5 h-3.5 text-rose-500" />
              高风险
            </div>
            <div className="mt-2 text-2xl font-semibold text-[#16271c]">{stats.high}</div>
          </div>
        </div>

        {/* 搜索 */}
        <div className="relative mb-6">
          <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="搜索技能名称、描述、分类或触发词…"
            className="w-full rounded-2xl border border-slate-200/70 bg-white/70 py-3 pl-11 pr-4 text-sm text-slate-700 outline-none backdrop-blur-sm transition-all placeholder:text-slate-400 focus:border-emerald-400 focus:bg-white"
          />
        </div>

        {/* 列表 */}
        <div className="space-y-8">
          {isLoading && !skills?.length ? (
            <LoadingGrid rows={3} cols={3} height="h-40" />
          ) : !isLoading && filtered.length === 0 ? (
            <EmptyState
              icon={Bot}
              title={search.trim() ? "未找到匹配技能" : "暂无已注册 Skill"}
              description={
                search.trim() ? "尝试更换搜索关键词" : "请检查后端 Skill 定义是否加载成功"
              }
            />
          ) : (
            categories.map(([category, group]) => (
              <section key={category}>
                <h2 className="mb-4 flex items-center gap-2 text-sm font-semibold text-slate-700">
                  <span className="h-4 w-1 rounded-full bg-emerald-500" />
                  {category}
                  <span className="text-xs font-normal text-slate-400">{group.length} 个</span>
                </h2>
                <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                  {group.map((skill) => {
                    const Icon = ICON_MAP[skill.icon] || Bot;
                    return (
                      <div
                        key={skill.name}
                        className="flex flex-col rounded-2xl border border-slate-200/60 bg-white/70 p-5 backdrop-blur-sm transition-all hover:border-emerald-300 hover:bg-white hover:shadow-md"
                      >
                        <div className="flex items-start gap-3">
                          <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-emerald-500/10 to-teal-500/10 text-emerald-600">
                            <Icon className="w-5 h-5" />
                          </div>
                          <div className="min-w-0 flex-1">
                            <div className="flex items-center gap-2 flex-wrap">
                              <h3 className="text-base font-semibold text-slate-800">
                                {skill.display_name}
                              </h3>
                              <span
                                className={`text-[10px] px-2 py-0.5 rounded-full border ${
                                  RISK_COLORS[skill.risk_level] || RISK_COLORS.low
                                }`}
                              >
                                {RISK_LABELS[skill.risk_level] || skill.risk_level}
                              </span>
                            </div>
                            {skill.tagline ? (
                              <p className="mt-1 text-sm font-medium text-emerald-700">
                                {skill.tagline}
                              </p>
                            ) : null}
                            <p className="mt-1.5 text-sm leading-relaxed text-slate-500">
                              {skill.description}
                            </p>
                          </div>
                        </div>

                        {skill.triggers && skill.triggers.length > 0 ? (
                          <div className="mt-4 flex flex-wrap gap-1.5">
                            {skill.triggers.slice(0, 8).map((t) => (
                              <span
                                key={t}
                                className="text-[11px] px-2 py-0.5 rounded-full bg-slate-100 text-slate-500"
                              >
                                {t}
                              </span>
                            ))}
                          </div>
                        ) : null}

                        {skill.examples && skill.examples.length > 0 ? (
                          <div className="mt-4 space-y-2">
                            <div className="text-xs font-medium text-slate-500 flex items-center gap-1">
                              <Zap className="w-3 h-3" />
                              一键体验
                            </div>
                            {skill.examples.map((ex) => (
                              <button
                                key={ex}
                                onClick={() => handleTry(ex)}
                                className="w-full text-left text-sm text-slate-500 hover:text-emerald-700 hover:bg-emerald-50/60 rounded-xl px-3 py-2 transition-colors border border-transparent hover:border-emerald-200"
                              >
                                {ex}
                              </button>
                            ))}
                          </div>
                        ) : null}

                        <div className="mt-auto pt-4 flex items-center justify-between text-xs text-slate-400">
                          <span>{skill.allowed_tools?.length || 0} 个可用工具</span>
                          <span>{skill.category || "通用"}</span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </section>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
