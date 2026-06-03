import {
  Search,
  BookOpen,
  Globe,
  Wrench,
  Brain,
  CheckCircle2,
  Loader2,
  AlertCircle,
  Database,
  User,
} from "lucide-react";

export interface ProgressStep {
  id: string;
  stage: string;
  label: string;
  detail?: string;
  status: "running" | "done" | "error" | "skipped";
  elapsed_ms?: number;
  data?: Record<string, unknown>;
}

interface Props {
  steps: ProgressStep[];
}

const STAGE_CONFIG: Record<
  string,
  { icon: typeof Search; color: string; bg: string }
> = {
  rewrite: { icon: Brain, color: "text-accent-purple", bg: "bg-accent-purple/10" },
  rewrite_done: { icon: Brain, color: "text-accent-purple", bg: "bg-accent-purple/10" },
  retrieve: { icon: BookOpen, color: "text-accent-blue", bg: "bg-accent-blue/10" },
  retrieve_done: { icon: BookOpen, color: "text-accent-blue", bg: "bg-accent-blue/10" },
  retrieve_degraded: { icon: AlertCircle, color: "text-accent-amber", bg: "bg-accent-amber/10" },
  web: { icon: Globe, color: "text-accent-amber", bg: "bg-accent-amber/10" },
  web_done: { icon: Globe, color: "text-accent-amber", bg: "bg-accent-amber/10" },
  web_degraded: { icon: AlertCircle, color: "text-accent-amber", bg: "bg-accent-amber/10" },
  user_context: { icon: User, color: "text-accent-green", bg: "bg-accent-green/10" },
  user_context_done: { icon: User, color: "text-accent-green", bg: "bg-accent-green/10" },
  llm_start: { icon: Brain, color: "text-accent-purple", bg: "bg-accent-purple/10" },
  tool_call: { icon: Wrench, color: "text-primary", bg: "bg-primary/10" },
  stats: { icon: Database, color: "text-text-muted", bg: "bg-bg-hover" },
};

export default function ProgressSteps({ steps }: Props) {
  if (!steps.length) return null;

  return (
    <div className="mb-3 px-1">
      <div className="flex flex-wrap gap-2">
        {steps.map((step) => {
          const cfg = STAGE_CONFIG[step.stage] || {
            icon: Search,
            color: "text-text-muted",
            bg: "bg-bg-hover",
          };
          const Icon = cfg.icon;

          return (
            <div
              key={step.id}
              className={`inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs border transition-all ${
                step.status === "running"
                  ? "border-primary/30 bg-primary/5"
                  : step.status === "error"
                  ? "border-accent-red/30 bg-accent-red/5"
                  : step.status === "skipped"
                  ? "border-border bg-bg-hover opacity-50"
                  : "border-border bg-bg-card"
              }`}
            >
              <div className={`p-0.5 rounded ${cfg.bg}`}>
                <Icon className={`w-3 h-3 ${cfg.color}`} />
              </div>
              <span
                className={`font-medium ${
                  step.status === "running"
                    ? "text-primary"
                    : step.status === "error"
                    ? "text-accent-red"
                    : "text-text-secondary"
                }`}
              >
                {step.label}
              </span>
              {step.detail && (
                <span className="text-text-muted max-w-[120px] truncate">
                  {step.detail}
                </span>
              )}
              {step.status === "running" ? (
                <Loader2 className="w-3 h-3 text-primary spinner" />
              ) : step.status === "done" ? (
                <CheckCircle2 className="w-3 h-3 text-accent-green" />
              ) : step.status === "error" ? (
                <AlertCircle className="w-3 h-3 text-accent-red" />
              ) : null}
              {step.elapsed_ms != null && step.elapsed_ms > 0 && (
                <span className="text-text-muted text-[10px]">
                  {step.elapsed_ms >= 1000
                    ? `${(step.elapsed_ms / 1000).toFixed(1)}s`
                    : `${step.elapsed_ms}ms`}
                </span>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

/** Convert raw SSE progress event to a ProgressStep */
export function toProgressStep(ev: Record<string, unknown>, index: number): ProgressStep {
  const stage = (ev.stage as string) || "unknown";
  const data = (ev.data || ev) as Record<string, unknown>;

  const statusMap: Record<string, ProgressStep["status"]> = {
    rewrite: "running",
    rewrite_done: "done",
    retrieve: "running",
    retrieve_done: "done",
    retrieve_degraded: "skipped",
    web: "running",
    web_done: "done",
    web_degraded: "skipped",
    user_context: "running",
    user_context_done: "done",
    llm_start: "done",
    tool_call: "done",
    stats: "done",
  };

  const labelMap: Record<string, string> = {
    rewrite: "理解问题",
    rewrite_done: "理解完成",
    retrieve: "检索知识库",
    retrieve_done: "知识库命中",
    retrieve_degraded: "知识库跳过",
    web: "联网搜索",
    web_done: "搜索完成",
    web_degraded: "搜索跳过",
    user_context: "加载农场数据",
    user_context_done: "农场数据就绪",
    llm_start: "生成回答",
    tool_call: `调用 ${data.name || "工具"}`,
    stats: "统计",
  };

  const detailMap: Record<string, string | undefined> = {
    rewrite_done: data.rewritten
      ? String(data.rewritten).slice(0, 30)
      : undefined,
    retrieve_done: data.hits
      ? `${(data.hits as unknown[]).length} 条结果`
      : data.top_k
      ? `top-${data.top_k}`
      : undefined,
    web_done: data.results
      ? `${(data.results as unknown[]).length} 条结果`
      : data.skip_reason
      ? String(data.skip_reason)
      : undefined,
    user_context_done: data.label ? String(data.label) : undefined,
    llm_start: undefined,
    tool_call: data.elapsed_ms
      ? `${data.elapsed_ms}ms`
      : data.status
      ? String(data.status)
      : undefined,
  };

  return {
    id: `${stage}-${index}`,
    stage,
    label: labelMap[stage] || stage,
    detail: detailMap[stage],
    status: statusMap[stage] || "done",
    elapsed_ms: data.elapsed_ms as number | undefined,
    data,
  };
}
