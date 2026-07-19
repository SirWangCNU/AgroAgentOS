import { useMemo } from "react";
import { AlertTriangle, Clock3, ShieldAlert, ShieldCheck } from "lucide-react";
import type { FarmActionProposal, FarmTask } from "../../types/farmAgent";

interface Props {
  proposals: FarmActionProposal[];
  tasks: FarmTask[];
}

interface ScoreBreakdown {
  highRisks: number;
  mediumRisks: number;
  overdueTasks: number;
  score: number;
}

function computeBreakdown(
  proposals: FarmActionProposal[],
  tasks: FarmTask[],
): ScoreBreakdown {
  const pending = proposals.filter((p) => p.status === "pending");
  const highRisks = pending.filter(
    (p) => p.severity === "high" || p.severity === "critical",
  ).length;
  const mediumRisks = pending.filter((p) => p.severity === "medium").length;
  const now = Date.now();
  const overdueTasks = tasks.filter((task) => {
    if (!task.due_at) return false;
    if (task.status === "completed" || task.status === "cancelled") return false;
    return new Date(task.due_at).getTime() < now;
  }).length;
  const raw = 100 - highRisks * 20 - mediumRisks * 10 - overdueTasks * 5;
  return { highRisks, mediumRisks, overdueTasks, score: Math.max(0, Math.min(100, raw)) };
}

function scoreTier(score: number): {
  color: string;
  ring: string;
  label: string;
  icon: typeof ShieldCheck;
} {
  if (score >= 80) {
    return {
      color: "#10b981",
      ring: "stroke-emerald-500",
      label: "健康",
      icon: ShieldCheck,
    };
  }
  if (score >= 60) {
    return {
      color: "#f59e0b",
      ring: "stroke-amber-500",
      label: "关注",
      icon: AlertTriangle,
    };
  }
  return {
    color: "#f43f5e",
    ring: "stroke-rose-500",
    label: "预警",
    icon: ShieldAlert,
  };
}

// 圆形进度条参数
const RADIUS = 52;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;

export default function HealthScoreCard({ proposals, tasks }: Props) {
  const breakdown = useMemo(
    () => computeBreakdown(proposals, tasks),
    [proposals, tasks],
  );
  const tier = scoreTier(breakdown.score);
  const Icon = tier.icon;
  const offset = CIRCUMFERENCE * (1 - breakdown.score / 100);

  const subMetrics = [
    {
      icon: ShieldAlert,
      label: "高风险提案",
      value: breakdown.highRisks,
      penalty: breakdown.highRisks * 20,
      color: "text-rose-600",
      bg: "bg-rose-50 border-rose-200",
    },
    {
      icon: AlertTriangle,
      label: "中风险提案",
      value: breakdown.mediumRisks,
      penalty: breakdown.mediumRisks * 10,
      color: "text-amber-600",
      bg: "bg-amber-50 border-amber-200",
    },
    {
      icon: Clock3,
      label: "逾期任务",
      value: breakdown.overdueTasks,
      penalty: breakdown.overdueTasks * 5,
      color: "text-orange-600",
      bg: "bg-orange-50 border-orange-200",
    },
  ];

  return (
    <section className="rounded-2xl border border-[#ded5c5] bg-[#fffdf7] p-4 shadow-[0_12px_36px_-30px_rgba(67,50,24,.65)]">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <span className="grid h-9 w-9 place-items-center rounded-xl bg-[#efe8d8] text-[#6f4d2c]">
            <ShieldCheck className="h-4 w-4" />
          </span>
          <div>
            <p className="text-[10px] font-bold uppercase tracking-[0.22em] text-[#8b785c]">
              Farm health score
            </p>
            <h2 className="text-sm font-semibold text-[#2e4036]">农场健康分</h2>
          </div>
        </div>
        <span
          className="rounded-full border px-2.5 py-1 text-[10px] font-bold"
          style={{ color: tier.color, borderColor: `${tier.color}40`, backgroundColor: `${tier.color}10` }}
        >
          {tier.label}
        </span>
      </div>

      <div className="mt-4 flex flex-col items-center gap-4 sm:flex-row sm:items-center">
        {/* 圆形进度条 */}
        <div className="relative h-32 w-32 shrink-0">
          <svg className="h-full w-full -rotate-90" viewBox="0 0 120 120">
            <circle
              cx="60"
              cy="60"
              r={RADIUS}
              fill="none"
              strokeWidth="10"
              className="stroke-[#efe8d8]"
            />
            <circle
              cx="60"
              cy="60"
              r={RADIUS}
              fill="none"
              strokeWidth="10"
              strokeLinecap="round"
              stroke={tier.color}
              strokeDasharray={CIRCUMFERENCE}
              strokeDashoffset={offset}
              style={{ transition: "stroke-dashoffset 0.6s ease" }}
            />
          </svg>
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <span
              className="text-3xl font-bold"
              style={{ color: tier.color }}
            >
              {breakdown.score}
            </span>
            <span className="text-[10px] text-[#8c8375]">分 / 100</span>
          </div>
        </div>

        {/* 子指标分解 */}
        <div className="flex-1 space-y-2">
          {subMetrics.map((metric) => (
            <div
              key={metric.label}
              className={`flex items-center justify-between rounded-xl border ${metric.bg} px-3 py-2`}
            >
              <div className="flex items-center gap-2">
                <metric.icon className={`h-3.5 w-3.5 ${metric.color}`} />
                <span className="text-xs font-medium text-[#34453b]">
                  {metric.label}
                </span>
              </div>
              <div className="flex items-center gap-2">
                <span className={`text-sm font-bold ${metric.color}`}>
                  {metric.value}
                </span>
                {metric.penalty > 0 && (
                  <span className="text-[10px] text-[#9a8c78]">
                    -{metric.penalty}
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="mt-3 flex items-start gap-2 rounded-lg bg-[#fbfaf5] px-3 py-2 text-[11px] leading-5 text-[#6f5c43]">
        <Icon className="mt-0.5 h-3.5 w-3.5 shrink-0" style={{ color: tier.color }} />
        <span>
          {breakdown.score >= 80
            ? "农场运行良好，无重大风险积压。建议保持例行巡检节奏。"
            : breakdown.score >= 60
              ? "存在中等风险或逾期任务，建议尽快处理待确认提案并跟踪任务进度。"
              : "高风险积压或任务逾期较多，请立即进入 AI 农场驾驶舱处理待办。"}
        </span>
      </div>
    </section>
  );
}

