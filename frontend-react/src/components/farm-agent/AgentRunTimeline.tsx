import { useMemo, useState } from "react";
import {
  Bot,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  CircleDot,
  FileText,
  GitBranch,
  ListChecks,
  Wrench,
  XCircle,
} from "lucide-react";
import type { FarmAgentEvent, FarmAgentRunStatus } from "../../types/farmAgent";

const icons = {
  skill_selected: Bot,
  plan: ListChecks,
  tool_call: Wrench,
  step_complete: CheckCircle2,
  replan: GitBranch,
  report: FileText,
  error: XCircle,
} as const;

interface Props {
  events: FarmAgentEvent[];
  status: FarmAgentRunStatus;
  riskCount?: number;
  proposalCount?: number;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function detailFor(event: FarmAgentEvent): string {
  if (event.type === "tool_call") {
    const name = event.data.name;
    const duration = event.data.duration_ms;
    const status = event.data.status;
    return [typeof name === "string" ? name : "受控工具", typeof status === "string" ? status : "", typeof duration === "number" ? `${duration} ms` : ""]
      .filter(Boolean)
      .join(" · ");
  }
  if ((event.type === "plan" || event.type === "replan") && Array.isArray(event.data.plan)) {
    return event.data.plan.filter((item): item is string => typeof item === "string").join(" → ");
  }
  if (event.type === "skill_selected" && typeof event.data.skill === "string") return event.data.skill;
  return event.stage.replaceAll("_", " ");
}

function PlanDetail({ plan }: { plan: unknown[] }) {
  const items = plan.filter((item): item is string => typeof item === "string");
  if (items.length === 0) return null;
  return (
    <ol className="mt-2 space-y-1.5 rounded-lg bg-white/5 p-2.5 text-xs text-[#b8d4c4]">
      {items.map((step, i) => (
        <li key={i} className="flex gap-2">
          <span className="shrink-0 rounded bg-white/10 px-1.5 py-0.5 text-[10px]">{i + 1}</span>
          <span className="leading-5">{step}</span>
        </li>
      ))}
    </ol>
  );
}

function ToolDetail({ data }: { data: Record<string, unknown> }) {
  const args = isRecord(data.args) ? data.args : {};
  const result = isRecord(data.result) ? data.result : {};
  const hasArgs = Object.keys(args).length > 0;
  const hasResult = Object.keys(result).length > 0;
  if (!hasArgs && !hasResult) return null;
  return (
    <div className="mt-2 space-y-2 rounded-lg bg-white/5 p-2.5 text-xs text-[#b8d4c4]">
      {hasArgs && (
        <div>
          <span className="text-[10px] uppercase tracking-wider text-[#759987]">参数</span>
          <pre className="mt-1 overflow-x-auto rounded bg-black/20 p-2 font-mono text-[11px]">
            {JSON.stringify(args, null, 2)}
          </pre>
        </div>
      )}
      {hasResult && (
        <div>
          <span className="text-[10px] uppercase tracking-wider text-[#759987]">返回</span>
          <pre className="mt-1 overflow-x-auto rounded bg-black/20 p-2 font-mono text-[11px]">
            {JSON.stringify(result, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}

function SkillDetail({ data }: { data: Record<string, unknown> }) {
  const reason = typeof data.reason === "string" ? data.reason : "";
  if (!reason) return null;
  return (
    <div className="mt-2 rounded-lg bg-white/5 p-2.5 text-xs text-[#b8d4c4]">
      <span className="text-[10px] uppercase tracking-wider text-[#759987]">选择理由</span>
      <p className="mt-1 leading-5">{reason}</p>
    </div>
  );
}

export default function AgentRunTimeline({ events, status, riskCount = 0, proposalCount = 0 }: Props) {
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const visibleEvents = events.filter((event) => !["step_token", "usage", "progress"].includes(event.type));

  const toggle = (eventId: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(eventId)) next.delete(eventId);
      else next.add(eventId);
      return next;
    });
  };

  const summary = useMemo(() => {
    if (status !== "completed") return null;
    return { riskCount, proposalCount };
  }, [status, riskCount, proposalCount]);

  return (
    <section aria-label="Agent 执行时间线" className="flex h-full flex-col rounded-2xl border border-[#244c3d] bg-[#102b23] text-[#edf5ed] shadow-[0_18px_50px_-28px_rgba(10,44,33,.8)]">
      <header className="flex items-center justify-between border-b border-white/10 px-5 py-4">
        <div>
          <p className="text-[10px] font-bold uppercase tracking-[0.24em] text-[#8fc4a8]">Agent trace</p>
          <h2 className="mt-1 text-base font-semibold">智能体执行轨迹</h2>
        </div>
        <span className="flex items-center gap-2 rounded-full bg-white/8 px-3 py-1 text-xs text-[#c7dfcf]">
          <span className={`h-2 w-2 rounded-full ${status === "running" ? "animate-pulse bg-[#f5b84b]" : status === "failed" ? "bg-red-400" : "bg-[#65b982]"}`} />
          {status === "running" ? "执行中" : status === "completed" ? "已收敛" : status === "failed" ? "异常" : "待命"}
        </span>
      </header>

      {summary && (
        <div className="mx-5 mt-4 flex items-center gap-3 rounded-lg border border-[#65b982]/30 bg-[#65b982]/10 px-3 py-2 text-xs text-[#a8e0bf]">
          <CheckCircle2 className="h-4 w-4 text-[#65b982]" />
          <span>
            巡检完成，生成 <strong className="text-white">{summary.riskCount}</strong> 条风险、
            <strong className="text-white">{summary.proposalCount}</strong> 项提案
          </span>
        </div>
      )}

      <div className="flex-1 overflow-y-auto px-5 py-4">
        {visibleEvents.length === 0 ? (
          <div className="flex min-h-48 flex-col items-center justify-center text-center text-[#8eaa99]">
            <CircleDot className="mb-3 h-7 w-7" />
            <p className="text-sm">启动巡检后，Skill、计划和工具调用会在这里实时展开。</p>
            <p className="mt-2 max-w-xs text-xs text-[#6f8a7a]">每一步都可点击展开，查看 Agent 调用了什么工具、拿到了什么结果。</p>
          </div>
        ) : (
          <ol className="relative space-y-1 before:absolute before:bottom-3 before:left-[13px] before:top-3 before:w-px before:bg-white/12">
            {visibleEvents.map((event, index) => {
              const Icon = icons[event.type as keyof typeof icons] ?? CircleDot;
              const isCurrent = status === "running" && index === visibleEvents.length - 1;
              const isExpanded = expanded.has(event.event_id);
              const expandable = ["tool_call", "plan", "replan", "skill_selected"].includes(event.type);
              return (
                <li key={event.event_id} className="relative flex gap-3 py-2">
                  <span className={`relative z-10 grid h-7 w-7 shrink-0 place-items-center rounded-full border ${event.type === "error" ? "border-red-400/60 bg-red-400/15 text-red-300" : isCurrent ? "border-[#f5b84b] bg-[#f5b84b]/15 text-[#ffd989]" : "border-[#477b62] bg-[#16392d] text-[#9bc9ad]"}`}>
                    <Icon className="h-3.5 w-3.5" aria-hidden="true" />
                  </span>
                  <div className="min-w-0 flex-1 pt-0.5">
                    <button
                      type="button"
                      onClick={() => expandable && toggle(event.event_id)}
                      className={`flex w-full items-start gap-1 text-left ${expandable ? "cursor-pointer" : "cursor-default"}`}
                    >
                      <p className={`text-sm font-medium ${event.type === "error" ? "text-red-300" : "text-[#f2f5ec]"}`}>
                        {event.message || detailFor(event)}
                      </p>
                      {expandable && (
                        <span className="mt-0.5 shrink-0 text-[#759987]">
                          {isExpanded ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
                        </span>
                      )}
                    </button>
                    <p className="mt-0.5 truncate text-[11px] uppercase tracking-[0.12em] text-[#759987]">{detailFor(event)}</p>
                    {isExpanded && event.type === "tool_call" && <ToolDetail data={event.data} />}
                    {isExpanded && (event.type === "plan" || event.type === "replan") && Array.isArray(event.data.plan) && <PlanDetail plan={event.data.plan} />}
                    {isExpanded && event.type === "skill_selected" && <SkillDetail data={event.data} />}
                  </div>
                </li>
              );
            })}
          </ol>
        )}
      </div>
    </section>
  );
}
