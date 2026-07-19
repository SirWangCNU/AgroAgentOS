import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  CheckCircle2,
  ClipboardList,
  History,
  Loader2,
  UserCircle2,
} from "lucide-react";
import { listFarmEvents } from "../../api/farmAgent";

interface Props {
  farmId: number | null;
  fieldId?: number;
  days?: number;
  refreshKey?: number;
  compact?: boolean;
  title?: string;
}

// 来源 → 颜色 + 图标 + 标签
const sourceStyle: Record<
  string,
  { icon: typeof CheckCircle2; dot: string; chip: string; label: string }
> = {
  task_completion: {
    icon: CheckCircle2,
    dot: "bg-emerald-500",
    chip: "bg-emerald-50 text-emerald-700 border-emerald-200",
    label: "任务完成",
  },
  human_entry: {
    icon: UserCircle2,
    dot: "bg-slate-400",
    chip: "bg-slate-50 text-slate-600 border-slate-200",
    label: "人工录入",
  },
  agent_run: {
    icon: History,
    dot: "bg-violet-500",
    chip: "bg-violet-50 text-violet-700 border-violet-200",
    label: "Agent 运行",
  },
};

const defaultSourceStyle = {
  icon: ClipboardList,
  dot: "bg-amber-500",
  chip: "bg-amber-50 text-amber-800 border-amber-200",
  label: "事件",
};

const eventTypeLabel: Record<string, string> = {
  spraying: "喷药",
  fertilizing: "施肥",
  irrigating: "灌溉",
  drainage: "排水",
  scouting: "巡田",
  sowing: "播种",
  harvesting: "收获",
  weeding: "除草",
  task_completed: "任务完成",
};

function formatEventTime(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return `${date.getFullYear()}/${date.getMonth() + 1}/${date.getDate()} ${String(date.getHours()).padStart(2, "0")}:${String(date.getMinutes()).padStart(2, "0")}`;
}

function summarizeInputs(inputs: unknown[]): string {
  if (!Array.isArray(inputs) || inputs.length === 0) return "";
  return inputs
    .map((item) => {
      if (typeof item === "string") return item;
      if (item && typeof item === "object") {
        const entries = Object.entries(item as Record<string, unknown>);
        if (entries.length === 0) return "";
        return entries
          .slice(0, 2)
          .map(([k, v]) => `${k}=${String(v)}`)
          .join(" ");
      }
      return String(item);
    })
    .filter(Boolean)
    .join(" · ");
}

export default function FarmEventTimeline({
  farmId,
  fieldId,
  days = 14,
  refreshKey = 0,
  compact = false,
  title,
}: Props) {
  const enabled = farmId !== null;
  const { data: events = [], isLoading } = useQuery({
    queryKey: ["farm-agent-events", farmId, fieldId ?? null, days, refreshKey],
    queryFn: () =>
      listFarmEvents({
        farm_id: farmId as number,
        ...(fieldId !== undefined ? { field_id: fieldId } : {}),
        days,
      }),
    enabled,
  });

  const sorted = useMemo(() => {
    // 后端已按 event_time desc 返回，这里保底再排一次
    return [...events].sort(
      (a, b) => new Date(b.event_time).getTime() - new Date(a.event_time).getTime(),
    );
  }, [events]);

  if (!enabled) {
    return (
      <section className="rounded-2xl border border-dashed border-[#d6cebf] bg-[#fbfaf5] px-4 py-8 text-center text-xs text-[#8c8375]">
        选择农场后展示事件时间线。
      </section>
    );
  }

  return (
    <section className="rounded-2xl border border-[#ded5c5] bg-[#fffdf7] p-4 shadow-[0_12px_36px_-30px_rgba(67,50,24,.65)]">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <span className="grid h-9 w-9 place-items-center rounded-xl bg-[#efe8d8] text-[#6f4d2c]">
            <History className="h-4 w-4" />
          </span>
          <div>
            <p className="text-[10px] font-bold uppercase tracking-[0.22em] text-[#8b785c]">
              Farm event timeline
            </p>
            <h2 className="text-sm font-semibold text-[#2e4036]">
              {title ?? `近 ${days} 天事件流`}
            </h2>
          </div>
        </div>
        <span className="rounded-full bg-[#efe8d8] px-2.5 py-1 text-[10px] font-bold text-[#6f4d2c]">
          {events.length} 条
        </span>
      </div>

      {isLoading ? (
        <div className="py-8 text-center text-xs text-[#8c8375]">
          <Loader2 className="mx-auto mb-2 h-4 w-4 animate-spin" />
          加载事件流…
        </div>
      ) : sorted.length === 0 ? (
        <div className="mt-3 rounded-xl border border-dashed border-[#d6cebf] bg-[#fbfaf5] px-4 py-8 text-center text-xs text-[#8c8375]">
          近 {days} 天暂无事件记录。任务完成或人工录入后将出现在这里。
        </div>
      ) : (
        <ol className={`mt-4 ${compact ? "space-y-2" : "space-y-3"}`}>
          {sorted.map((event) => {
            const style = sourceStyle[event.source] ?? defaultSourceStyle;
            const Icon = style.icon;
            const typeLabel = eventTypeLabel[event.event_type] ?? event.event_type;
            const inputSummary = summarizeInputs(event.inputs);
            return (
              <li
                key={event.id}
                className={`relative flex items-start gap-3 ${compact ? "" : "rounded-xl border border-[#ece5d8] bg-white/80 p-3"}`}
              >
                <span className="mt-1 flex flex-col items-center">
                  <span className={`grid h-7 w-7 place-items-center rounded-full ${style.dot} text-white`}>
                    <Icon className="h-3.5 w-3.5" />
                  </span>
                  {!compact && (
                    <span className="mt-1 w-px flex-1 bg-[#ece5d8]" />
                  )}
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className={`rounded-full border px-2 py-0.5 text-[10px] font-bold ${style.chip}`}>
                      {typeLabel}
                    </span>
                    <span className="text-[10px] text-[#9a8c78]">
                      {formatEventTime(event.event_time)}
                    </span>
                    <span className="text-[10px] text-[#806c54]">
                      操作人 {event.operator}
                    </span>
                  </div>
                  {event.note && (
                    <p className="mt-1 text-xs leading-5 text-[#4c554e]">
                      {event.note}
                    </p>
                  )}
                  {inputSummary && (
                    <p className="mt-1 text-[10px] text-[#9a8c78]">
                      投入：{inputSummary}
                    </p>
                  )}
                  {event.related_task_id && (
                    <p className="mt-1 text-[10px] text-[#597461]">
                      关联任务 {event.related_task_id}
                    </p>
                  )}
                </div>
              </li>
            );
          })}
        </ol>
      )}
    </section>
  );
}
