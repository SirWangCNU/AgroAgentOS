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
  Megaphone,
  Radar,
  ClipboardCheck,
  Sparkles,
  Search,
  ArrowRight,
  Zap,
  LayoutDashboard,
  ShieldCheck,
  AlertTriangle,
} from "lucide-react";
import { useHealthStore } from "../stores/health";
import { getSkills } from "../api/health";
import type { Skill } from "../types/api";
import WorkspaceLayout from "../components/layout/WorkspaceLayout";
import LoadingGrid from "../components/ui/LoadingGrid";
import EmptyState from "../components/ui/EmptyState";
import StatCard from "../components/ui/StatCard";

const ICON_MAP: Record<string, React.ElementType> = {
  Bot,
  CloudSun,
  Sprout,
  Bug,
  MessageSquare,
  TrendingUp,
  BookOpen,
  Megaphone,
  Radar,
  ClipboardCheck,
  Sparkles,
};

const RISK_COLORS: Record<string, string> = {
  low: "text-accent-green bg-accent-green/10",
  medium: "text-accent-amber bg-accent-amber/10",
  high: "text-accent-red bg-accent-red/10",
};

const RISK_LABELS: Record<string, string> = {
  low: "低风险",
  medium: "中风险",
  high: "高风险",
};

export default function AgentCapabilities() {
  const navigate = useNavigate();
  const [search, setSearch] = useState("");
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
    navigate("/", { state: { initialMessage: example } });
  };

  return (
    <WorkspaceLayout
      title="智能体能力中心"
      icon={Bot}
      iconColor="text-primary"
      description="查看全部已注册 Skill，点击示例问题即可一键体验对应智能体能力"
      action={
        <button
          onClick={() => navigate("/workspace/dashboard")}
          className="inline-flex items-center gap-1.5 text-sm font-medium text-text-secondary hover:text-primary transition-colors"
        >
          数据仪表盘 <ArrowRight className="w-4 h-4" />
        </button>
      }
    >
      {/* Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
        <StatCard
          icon={LayoutDashboard}
          label="已注册 Skill"
          value={stats.total}
          color="text-primary"
        />
        <StatCard
          icon={ShieldCheck}
          label="低风险"
          value={stats.low}
          color="text-accent-green"
        />
        <StatCard
          icon={Zap}
          label="中风险"
          value={stats.medium}
          color="text-accent-amber"
        />
        <StatCard
          icon={AlertTriangle}
          label="高风险"
          value={stats.high}
          color="text-accent-red"
        />
      </div>

      {/* Search */}
      <div className="relative mb-6">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="搜索技能名称、描述、分类或触发词…"
          className="w-full pl-9 pr-4 py-2.5 text-sm bg-bg-card border border-border rounded-xl outline-none focus:border-primary transition-colors"
        />
      </div>

      {/* Loading */}
      {isLoading && !skills?.length ? (
        <LoadingGrid rows={3} cols={3} height="h-40" />
      ) : null}

      {/* Empty */}
      {!isLoading && filtered.length === 0 ? (
        <EmptyState
          icon={Bot}
          title={search.trim() ? "未找到匹配技能" : "暂无已注册 Skill"}
          description={
            search.trim()
              ? "尝试更换搜索关键词"
              : "请检查后端 Skill 定义是否加载成功"
          }
        />
      ) : null}

      {/* Categories */}
      <div className="space-y-8">
        {categories.map(([category, group]) => (
          <section key={category}>
            <h2 className="text-sm font-semibold text-text-secondary mb-3 flex items-center gap-2">
              <span className="w-1 h-4 rounded-full bg-primary" />
              {category}
              <span className="text-xs font-normal text-text-muted">
                {group.length} 个
              </span>
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
              {group.map((skill) => {
                const Icon = ICON_MAP[skill.icon] || Bot;
                return (
                  <div
                    key={skill.name}
                    className="flex flex-col rounded-2xl border border-border bg-bg-card p-5 hover:border-primary/40 hover:shadow-md transition-all"
                  >
                    <div className="flex items-start gap-3">
                      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
                        <Icon className="w-5 h-5" />
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2 flex-wrap">
                          <h3 className="text-base font-semibold text-text-primary">
                            {skill.display_name}
                          </h3>
                          <span
                            className={`text-[10px] px-2 py-0.5 rounded-full ${
                              RISK_COLORS[skill.risk_level] || RISK_COLORS.low
                            }`}
                          >
                            {RISK_LABELS[skill.risk_level] ||
                              skill.risk_level}
                          </span>
                        </div>
                        {skill.tagline ? (
                          <p className="mt-1 text-sm font-medium text-primary">
                            {skill.tagline}
                          </p>
                        ) : null}
                        <p className="mt-1.5 text-sm text-text-secondary leading-relaxed">
                          {skill.description}
                        </p>
                      </div>
                    </div>

                    {skill.triggers && skill.triggers.length > 0 ? (
                      <div className="mt-4 flex flex-wrap gap-1.5">
                        {skill.triggers.slice(0, 8).map((t) => (
                          <span
                            key={t}
                            className="text-[11px] px-2 py-0.5 rounded-full bg-bg-hover text-text-muted"
                          >
                            {t}
                          </span>
                        ))}
                      </div>
                    ) : null}

                    {skill.examples && skill.examples.length > 0 ? (
                      <div className="mt-4 space-y-2">
                        <div className="text-xs font-medium text-text-secondary flex items-center gap-1">
                          <Zap className="w-3 h-3" />
                          一键体验
                        </div>
                        {skill.examples.map((ex) => (
                          <button
                            key={ex}
                            onClick={() => handleTry(ex)}
                            className="w-full text-left text-sm text-text-secondary hover:text-primary hover:bg-primary-light rounded-lg px-3 py-2 transition-colors border border-border hover:border-primary/30"
                          >
                            {ex}
                          </button>
                        ))}
                      </div>
                    ) : null}

                    <div className="mt-auto pt-4 flex items-center justify-between text-xs text-text-muted">
                      <span>
                        {skill.allowed_tools?.length || 0} 个可用工具
                      </span>
                      <span>{skill.category || "通用"}</span>
                    </div>
                  </div>
                );
              })}
            </div>
          </section>
        ))}
      </div>
    </WorkspaceLayout>
  );
}
