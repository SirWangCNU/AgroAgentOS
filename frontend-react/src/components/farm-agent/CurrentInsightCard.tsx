import { useState } from "react";
import { AlertTriangle, Bot, CheckCircle2, ClipboardCheck, Gauge, XCircle } from "lucide-react";
import type { FarmActionProposal, FarmRisk, ProposedAction } from "../../types/farmAgent";

interface RiskInsightProps {
  type: "risk";
  data: FarmRisk;
}

interface ProposalInsightProps {
  type: "proposal";
  data: FarmActionProposal;
  busy?: boolean;
  onApprove: (actions: ProposedAction[], note: string) => void;
  onReject: (note: string) => void;
}

type Props = RiskInsightProps | ProposalInsightProps;

const severityStyle = {
  low: "bg-emerald-50 text-emerald-700 border-emerald-200",
  medium: "bg-amber-50 text-amber-800 border-amber-200",
  high: "bg-orange-50 text-orange-800 border-orange-200",
  critical: "bg-red-50 text-red-800 border-red-200",
} as const;

const factLabels = { measured: "实测", rule: "规则", inference: "推断" } as const;

export function EmptyInsight() {
  return (
    <div className="flex h-full flex-col items-center justify-center rounded-2xl border border-dashed border-slate-200 bg-slate-50/50 px-4 py-10 text-center">
      <Bot className="h-8 w-8 text-slate-300" />
      <p className="mt-3 text-sm font-medium text-slate-600">暂无当前洞察</p>
      <p className="mt-1 text-xs text-slate-400">启动巡检后，AI 发现的最高优先级风险会出现在这里。</p>
    </div>
  );
}

function RiskInsight({ risk }: { risk: FarmRisk }) {
  return (
    <article className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2">
          <span className="grid h-9 w-9 place-items-center rounded-xl bg-amber-50 text-amber-600">
            <AlertTriangle className="h-5 w-5" />
          </span>
          <div>
            <p className="text-[10px] font-bold uppercase tracking-wider text-slate-400">当前风险</p>
            <h3 className="text-sm font-semibold text-slate-800">{risk.risk_key.replaceAll(/[._:]/g, " ")}</h3>
          </div>
        </div>
        <span className={`rounded-full border px-2.5 py-1 text-[10px] font-bold uppercase tracking-wider ${severityStyle[risk.severity]}`}>
          {risk.severity}
        </span>
      </div>

      <div className="mt-3 flex items-center gap-2 text-xs text-slate-500">
        <Gauge className="h-3.5 w-3.5" />
        <span>置信度 {Math.round(risk.confidence * 100)}%</span>
        <span className="text-slate-300">·</span>
        <span>{risk.evidence.length} 条证据</span>
      </div>

      {risk.evidence.length > 0 && (
        <div className="mt-3 rounded-xl border border-slate-100 bg-slate-50/70 p-3">
          <div className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-wider text-slate-400">
            <span className="rounded bg-white px-1.5 py-0.5 text-[#3d6a51]">{factLabels[risk.evidence[0].fact_kind]}</span>
            <span>关键证据</span>
          </div>
          <p className="mt-1.5 text-xs leading-5 text-slate-600">{risk.evidence[0].summary}</p>
        </div>
      )}

      {risk.suggested_actions.length > 0 && (
        <div className="mt-3 flex items-start gap-2 text-xs leading-5 text-slate-600">
          <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-600" />
          <span>{risk.suggested_actions[0]}</span>
        </div>
      )}
    </article>
  );
}

function ProposalInsight({ proposal, busy, onApprove, onReject }: { proposal: FarmActionProposal; busy?: boolean; onApprove: (actions: ProposedAction[], note: string) => void; onReject: (note: string) => void }) {
  const [note, setNote] = useState("");
  return (
    <article className="rounded-2xl border border-amber-200 bg-[#fffdf8] p-4 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2">
          <span className="grid h-9 w-9 place-items-center rounded-xl bg-amber-100 text-amber-700">
            <ClipboardCheck className="h-5 w-5" />
          </span>
          <div>
            <p className="text-[10px] font-bold uppercase tracking-wider text-amber-600/70">待确认行动</p>
            <h3 className="text-sm font-semibold text-slate-800">{proposal.title}</h3>
          </div>
        </div>
        <span className="rounded-full border border-amber-300 bg-amber-50 px-2.5 py-1 text-[10px] font-bold uppercase tracking-wider text-amber-800">
          待确认
        </span>
      </div>

      <p className="mt-2 text-xs leading-5 text-slate-600 line-clamp-3">{proposal.summary}</p>

      <div className="mt-3 flex items-center gap-2 text-xs text-slate-500">
        <Gauge className="h-3.5 w-3.5" />
        <span>置信度 {Math.round(proposal.confidence * 100)}%</span>
        <span className="text-slate-300">·</span>
        <span>{proposal.evidence.length} 条证据</span>
        <span className="text-slate-300">·</span>
        <span>{proposal.actions.length} 项行动</span>
      </div>

      {proposal.evidence.length > 0 && (
        <div className="mt-3 rounded-xl border border-amber-100 bg-white/70 p-3">
          <p className="text-[10px] font-bold uppercase tracking-wider text-amber-700/70">关键证据</p>
          <p className="mt-1 text-xs leading-5 text-slate-600">{proposal.evidence[0].summary}</p>
        </div>
      )}

      <div className="mt-3 space-y-2">
        <input
          type="text"
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder="审批备注（可选）"
          className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs outline-none focus:border-emerald-400"
        />
        <div className="flex items-center gap-2">
          <button
            type="button"
            disabled={busy}
            onClick={() => onApprove(proposal.actions, note)}
            className="flex flex-1 items-center justify-center gap-1.5 rounded-lg bg-emerald-600 px-3 py-2 text-xs font-semibold text-white hover:bg-emerald-700 disabled:opacity-50"
          >
            {busy ? <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-white/30 border-t-white" /> : <CheckCircle2 className="h-3.5 w-3.5" />}
            批准并生成任务
          </button>
          <button
            type="button"
            disabled={busy}
            onClick={() => onReject(note)}
            className="flex items-center justify-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-50 disabled:opacity-50"
          >
            <XCircle className="h-3.5 w-3.5" />
            拒绝
          </button>
        </div>
      </div>
    </article>
  );
}

export default function CurrentInsightCard(props: Props) {
  if (props.type === "risk") {
    return <RiskInsight risk={props.data} />;
  }
  return <ProposalInsight proposal={props.data} busy={props.busy} onApprove={props.onApprove} onReject={props.onReject} />;
}
