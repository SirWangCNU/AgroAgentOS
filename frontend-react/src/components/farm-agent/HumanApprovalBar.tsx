import { useState } from "react";
import { Check, Loader2, ShieldCheck, X } from "lucide-react";
import type { FarmActionProposal, ProposedAction } from "../../types/farmAgent";

interface Props {
  proposal: FarmActionProposal;
  busy: boolean;
  onApprove: (actions: ProposedAction[], note: string) => void;
  onReject: (note: string) => void;
}

export default function HumanApprovalBar({ proposal, busy, onApprove, onReject }: Props) {
  const [actions, setActions] = useState(proposal.actions);
  const [selected, setSelected] = useState(() => new Set(proposal.actions.map((action) => action.action_key)));
  const [note, setNote] = useState("");

  const updateAction = (key: string, patch: Partial<ProposedAction>) => {
    setActions((current) => current.map((action) => action.action_key === key ? { ...action, ...patch } : action));
  };

  const toggle = (key: string) => {
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(key)) next.delete(key); else next.add(key);
      return next;
    });
  };

  const chosen = actions.filter((action) => selected.has(action.action_key));
  return (
    <div className="mt-4 border-t border-[#e3d7c2] pt-4">
      <div className="mb-3 flex items-center gap-2 text-xs font-semibold text-[#28533f]"><ShieldCheck className="h-4 w-4" />人工决策门</div>
      <div className="space-y-3">
        {actions.map((action) => (
          <div key={action.action_key} className={`rounded-xl border p-3 transition ${selected.has(action.action_key) ? "border-[#95b8a2] bg-[#f4f8f3]" : "border-[#e5dfd3] bg-[#f7f5ef] opacity-60"}`}>
            <label className="flex cursor-pointer items-start gap-2 text-sm font-medium text-[#2b3d32]">
              <input aria-label={`选择 ${action.title}`} type="checkbox" checked={selected.has(action.action_key)} onChange={() => toggle(action.action_key)} className="mt-1 accent-[#1f6a4b]" />
              {action.title}
            </label>
            {selected.has(action.action_key) && <div className="mt-3 grid gap-2 sm:grid-cols-2">
              <label className="text-[11px] text-[#776b59]">执行人<input value={action.assignee_name} onChange={(e) => updateAction(action.action_key, { assignee_name: e.target.value })} className="mt-1 w-full rounded-lg border border-[#d9d2c6] bg-white px-2.5 py-2 text-xs outline-none focus:border-[#3f7f61]" /></label>
              <label className="text-[11px] text-[#776b59]">截止时间<input type="datetime-local" value={action.due_at?.slice(0, 16) ?? ""} onChange={(e) => updateAction(action.action_key, { due_at: e.target.value || null })} className="mt-1 w-full rounded-lg border border-[#d9d2c6] bg-white px-2.5 py-2 text-xs outline-none focus:border-[#3f7f61]" /></label>
              <label className="text-[11px] text-[#776b59] sm:col-span-2">作业指令<textarea value={action.instructions} onChange={(e) => updateAction(action.action_key, { instructions: e.target.value })} rows={2} className="mt-1 w-full resize-none rounded-lg border border-[#d9d2c6] bg-white px-2.5 py-2 text-xs outline-none focus:border-[#3f7f61]" /></label>
            </div>}
          </div>
        ))}
      </div>
      <textarea aria-label="决策说明" value={note} onChange={(e) => setNote(e.target.value)} placeholder="填写批准或拒绝说明（进入审计记录）" rows={2} className="mt-3 w-full resize-none rounded-xl border border-[#d9d2c6] bg-white px-3 py-2 text-xs outline-none focus:border-[#3f7f61]" />
      <div className="mt-3 flex flex-wrap justify-end gap-2">
        <button type="button" disabled={busy} onClick={() => onReject(note)} className="inline-flex items-center gap-1.5 rounded-lg border border-red-200 px-3 py-2 text-xs font-semibold text-red-700 hover:bg-red-50 disabled:opacity-50"><X className="h-3.5 w-3.5" />拒绝提案</button>
        <button type="button" disabled={busy || chosen.length === 0} onClick={() => onApprove(chosen, note)} className="inline-flex items-center gap-1.5 rounded-lg bg-[#1f6a4b] px-3 py-2 text-xs font-semibold text-white hover:bg-[#184f39] disabled:opacity-50">{busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Check className="h-3.5 w-3.5" />}批准 {chosen.length} 项</button>
      </div>
    </div>
  );
}
