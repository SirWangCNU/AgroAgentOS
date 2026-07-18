import { useEffect, useRef, useState } from "react";
import { Bot, CheckCircle2, Loader2, RotateCcw, ShieldAlert } from "lucide-react";
import { streamFarmTaskVerification } from "../../api/farmTasks";
import type { FarmTask, TaskVerificationDraft, VerificationVerdict } from "../../types/farmAgent";

interface Props {
  task: FarmTask;
  busy: boolean;
  onComplete: (note: string) => void;
  onReturn: (note: string) => void;
}

function readVerdict(value: unknown): TaskVerificationDraft | null {
  if (typeof value !== "object" || value === null) return null;
  const record = value as Record<string, unknown>;
  const allowed: VerificationVerdict[] = ["pass", "needs_evidence", "rework", "manual_review"];
  if (!allowed.some((item) => item === record.verdict) || typeof record.note !== "string") return null;
  return { verdict: record.verdict as VerificationVerdict, note: record.note, evidence_refs: Array.isArray(record.evidence_refs) ? record.evidence_refs.filter((item): item is string => typeof item === "string") : [] };
}

export default function TaskVerificationCard({ task, busy, onComplete, onReturn }: Props) {
  const controllerRef = useRef<AbortController | null>(null);
  const [running, setRunning] = useState(false);
  const [verdict, setVerdict] = useState<TaskVerificationDraft | null>(() => readVerdict(task.agent_verdict));
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);
  useEffect(() => () => controllerRef.current?.abort(), []);

  const verify = async () => {
    controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;
    setRunning(true); setError(null);
    try {
      for await (const event of streamFarmTaskVerification(task.task_id, controller.signal)) {
        const outcome = typeof event.data.outcome === "object" && event.data.outcome !== null ? event.data.outcome as Record<string, unknown> : null;
        const next = readVerdict(outcome?.task_verdict);
        if (next) setVerdict(next);
        if (event.type === "error") setError(event.message || "AI 复核未完成");
      }
    } catch (caught) {
      if (!(caught instanceof DOMException && caught.name === "AbortError")) setError(caught instanceof Error ? caught.message : "AI 复核失败");
    } finally { setRunning(false); }
  };

  return (
    <div className="mt-3 rounded-xl border border-[#c9d9cd] bg-[#f5faf6] p-3">
      <div className="flex items-center justify-between gap-2"><span className="flex items-center gap-2 text-xs font-semibold text-[#24513c]"><Bot className="h-4 w-4" />AI 验收草稿</span><button type="button" onClick={verify} disabled={running} className="rounded-lg border border-[#aac5b3] px-2.5 py-1.5 text-[11px] font-semibold text-[#24513c] hover:bg-white disabled:opacity-50">{running ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : verdict ? "重新复核" : "开始复核"}</button></div>
      {error && <p className="mt-2 text-xs text-red-700">{error}</p>}
      {verdict && <div className="mt-3">
        <div className="flex items-center gap-2"><span className="rounded-full bg-[#dbeade] px-2 py-1 text-[10px] font-bold uppercase text-[#24513c]">{verdict.verdict}</span><span className="text-[11px] text-[#718074]">覆盖 {verdict.evidence_refs.length} 项证据</span></div>
        <p className="mt-2 text-xs leading-5 text-[#46584b]">{verdict.note}</p>
        {verdict.verdict !== "pass" && <p className="mt-2 text-[11px] font-semibold text-amber-800">存在证据缺口或需要现场复查，请勿直接完成任务。</p>}
        <div className="mt-3 rounded-lg bg-amber-50 px-3 py-2 text-[11px] text-amber-800"><ShieldAlert className="mr-1 inline h-3.5 w-3.5" />AI 只给出草稿，任务仍为 submitted，必须人工决策。</div>
        <textarea value={note} onChange={(e) => setNote(e.target.value)} placeholder="填写人工验收说明" rows={2} className="mt-3 w-full resize-none rounded-lg border border-[#cbd7cd] bg-white px-2.5 py-2 text-xs outline-none focus:border-[#3f7f61]" />
        <div className="mt-2 flex justify-end gap-2"><button type="button" disabled={busy} onClick={() => onReturn(note)} className="inline-flex items-center gap-1 rounded-lg border border-amber-300 px-2.5 py-1.5 text-[11px] font-semibold text-amber-800"><RotateCcw className="h-3.5 w-3.5" />退回整改</button>{(verdict.verdict === "pass" || verdict.verdict === "manual_review") && <button type="button" disabled={busy} onClick={() => onComplete(note)} className="inline-flex items-center gap-1 rounded-lg bg-[#1f6a4b] px-2.5 py-1.5 text-[11px] font-semibold text-white"><CheckCircle2 className="h-3.5 w-3.5" />人工完成</button>}</div>
      </div>}
    </div>
  );
}
