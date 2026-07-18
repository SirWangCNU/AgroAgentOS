import { ClipboardCheck, Gauge } from "lucide-react";
import type { FarmActionProposal, ProposedAction } from "../../types/farmAgent";
import HumanApprovalBar from "./HumanApprovalBar";

interface Props {
  proposal: FarmActionProposal;
  busy: boolean;
  onApprove: (actions: ProposedAction[], note: string) => void;
  onReject: (note: string) => void;
}

export default function ActionProposalCard(props: Props) {
  const { proposal } = props;
  return (
    <article className="rounded-2xl border border-[#ddd1bd] bg-[#fffaf0] p-4 shadow-[0_16px_48px_-34px_rgba(75,52,18,.8)]">
      <div className="flex items-start justify-between gap-3">
        <span className="grid h-10 w-10 place-items-center rounded-xl bg-[#efe1c4] text-[#865b22]"><ClipboardCheck className="h-5 w-5" /></span>
        <span className="rounded-full border border-amber-300 bg-amber-50 px-2.5 py-1 text-[10px] font-bold uppercase tracking-widest text-amber-800">待确认</span>
      </div>
      <h3 className="mt-3 text-base font-semibold text-[#263a30]">{proposal.title}</h3>
      <p className="mt-1.5 text-xs leading-5 text-[#6c6558]">{proposal.summary}</p>
      <div className="mt-3 flex items-center gap-3 rounded-xl bg-white/70 px-3 py-2 text-xs text-[#675b49]">
        <Gauge className="h-4 w-4 text-[#b37728]" /><span>置信度 {Math.round(proposal.confidence * 100)}%</span><span>·</span><span>{proposal.evidence.length} 条证据</span><span>·</span><span>{proposal.actions.length} 项行动</span>
      </div>
      <div className="mt-3 space-y-1.5">
        {proposal.evidence.slice(0, 3).map((evidence) => <div key={`${evidence.source_type}-${evidence.source_id}`} className="flex items-start gap-2 rounded-lg border border-[#e8dfcf] bg-white/60 px-2.5 py-2 text-[11px] leading-4 text-[#625b4f]"><span className="shrink-0 rounded bg-[#e8efe8] px-1.5 py-0.5 font-bold uppercase text-[#3d6a51]">{evidence.fact_kind}</span><span>{evidence.summary}</span></div>)}
      </div>
      <HumanApprovalBar {...props} />
    </article>
  );
}
