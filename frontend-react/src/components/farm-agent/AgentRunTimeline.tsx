import {
  Bot,
  CheckCircle2,
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
}

function detailFor(event: FarmAgentEvent): string {
  if (event.type === "tool_call") {
    const name = event.data.name;
    const duration = event.data.duration_ms;
    return [typeof name === "string" ? name : "受控工具", typeof duration === "number" ? `${duration} ms` : ""]
      .filter(Boolean)
      .join(" · ");
  }
  if (event.type === "skill_selected" && typeof event.data.skill === "string") return event.data.skill;
  return event.stage.replaceAll("_", " ");
}

export default function AgentRunTimeline({ events, status }: Props) {
  return (
    <section aria-label="Agent 执行时间线" className="h-full rounded-2xl border border-[#244c3d] bg-[#102b23] text-[#edf5ed] shadow-[0_18px_50px_-28px_rgba(10,44,33,.8)]">
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
      <div className="max-h-[34rem] overflow-y-auto px-5 py-4">
        {events.length === 0 ? (
          <div className="flex min-h-48 flex-col items-center justify-center text-center text-[#8eaa99]">
            <CircleDot className="mb-3 h-7 w-7" />
            <p className="text-sm">启动巡检后，Skill、计划和工具调用会在这里实时展开。</p>
          </div>
        ) : (
          <ol className="relative space-y-1 before:absolute before:bottom-3 before:left-[13px] before:top-3 before:w-px before:bg-white/12">
            {events.map((event, index) => {
              const Icon = icons[event.type as keyof typeof icons] ?? CircleDot;
              const isCurrent = status === "running" && index === events.length - 1;
              return (
                <li key={event.event_id} className="relative flex gap-3 py-2.5">
                  <span className={`relative z-10 grid h-7 w-7 shrink-0 place-items-center rounded-full border ${event.type === "error" ? "border-red-400/60 bg-red-400/15 text-red-300" : isCurrent ? "border-[#f5b84b] bg-[#f5b84b]/15 text-[#ffd989]" : "border-[#477b62] bg-[#16392d] text-[#9bc9ad]"}`}>
                    <Icon className="h-3.5 w-3.5" aria-hidden="true" />
                  </span>
                  <div className="min-w-0 pt-0.5">
                    <p className="text-sm font-medium text-[#f2f5ec]">{event.message || detailFor(event)}</p>
                    <p className="mt-1 truncate text-[11px] uppercase tracking-[0.12em] text-[#759987]">{detailFor(event)}</p>
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
