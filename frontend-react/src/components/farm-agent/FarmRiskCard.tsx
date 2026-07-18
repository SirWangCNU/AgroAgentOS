import { AlertTriangle, CloudRain, DatabaseZap, Route } from "lucide-react";
import type { FarmRisk } from "../../types/farmAgent";

const severityStyle = {
  low: "bg-emerald-50 text-emerald-700 border-emerald-200",
  medium: "bg-amber-50 text-amber-800 border-amber-200",
  high: "bg-orange-50 text-orange-800 border-orange-200",
  critical: "bg-red-50 text-red-800 border-red-200",
};

const factLabels = { measured: "实测", rule: "规则", inference: "推断" } as const;

interface Props {
  risk: FarmRisk;
  degraded?: boolean;
}

export default function FarmRiskCard({ risk, degraded = false }: Props) {
  const WeatherIcon = risk.risk_key.includes("weather") ? CloudRain : Route;
  return (
    <article className="rounded-2xl border border-[#ded5c5] bg-[#fffdf7] p-4 shadow-[0_12px_36px_-30px_rgba(67,50,24,.65)]">
      <div className="flex items-start justify-between gap-3">
        <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-[#efe8d8] text-[#6f4d2c]"><WeatherIcon className="h-5 w-5" /></span>
        <span className={`rounded-full border px-2.5 py-1 text-[10px] font-bold uppercase tracking-[0.16em] ${severityStyle[risk.severity]}`}>{risk.severity}</span>
      </div>
      <h3 className="mt-3 text-sm font-semibold text-[#23372d]">{risk.risk_key.replaceAll(/[._:]/g, " ")}</h3>
      <div className="mt-2 flex items-center gap-2 text-xs text-[#806c54]">
        <span>置信度 {Math.round(risk.confidence * 100)}%</span><span>·</span><span>{risk.evidence.length} 条证据</span>
      </div>
      <div className="mt-3 space-y-2">
        {risk.evidence.map((evidence) => (
          <div key={`${evidence.source_type}-${evidence.source_id}`} className="rounded-xl border border-[#ece5d8] bg-white/80 p-3">
            <div className="flex items-center justify-between gap-2">
              <span className="text-[10px] font-bold uppercase tracking-wider text-[#597461]">{factLabels[evidence.fact_kind]}</span>
              <span className="truncate text-[10px] text-[#9a8c78]">{evidence.source_type}</span>
            </div>
            <p className="mt-1.5 text-xs leading-5 text-[#4c554e]">{evidence.summary}</p>
          </div>
        ))}
      </div>
      {degraded && <div className="mt-3 flex items-center gap-2 rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-800"><DatabaseZap className="h-4 w-4" />数据缺口，结论已降级</div>}
      {risk.suggested_actions.length > 0 && <div className="mt-3 flex items-start gap-2 text-xs leading-5 text-[#6f5c43]"><AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-[#d89127]" /><span>{risk.suggested_actions[0]}</span></div>}
    </article>
  );
}
