import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bot, CloudRain, Loader2, Radar, Sparkles, Tractor } from "lucide-react";
import { getFarms } from "../api/farms";
import { ApiError } from "../api/client";
import { approveFarmProposal, getFarmRunTimeline, listFarmProposals, rejectFarmProposal, streamFarmInspection } from "../api/farmAgent";
import { completeFarmTask, listFarmTasks, returnFarmTask, startFarmTask, submitFarmTask } from "../api/farmTasks";
import { useFarmAgentStore } from "../stores/farmAgent";
import { useUIStore } from "../stores/ui";
import type { FarmRisk, ProposedAction, TaskSubmitRequest } from "../types/farmAgent";
import WorkspaceLayout from "../components/layout/WorkspaceLayout";
import AgentRunTimeline from "../components/farm-agent/AgentRunTimeline";
import FarmRiskCard from "../components/farm-agent/FarmRiskCard";
import ActionProposalCard from "../components/farm-agent/ActionProposalCard";
import FarmTaskBoard from "../components/farm-agent/FarmTaskBoard";

function proposalRisk(proposal: Awaited<ReturnType<typeof listFarmProposals>>[number]): FarmRisk {
  return { risk_key: proposal.risk_fingerprint, severity: proposal.severity, confidence: proposal.confidence, evidence: proposal.evidence, suggested_actions: proposal.actions.map((action) => action.title) };
}

export default function FarmAgent() {
  const [searchParams] = useSearchParams();
  const queryClient = useQueryClient();
  const showToast = useUIStore((state) => state.showToast);
  const abortRef = useRef<AbortController | null>(null);
  const [selectedFarmId, setSelectedFarmId] = useState<number | null>(null);
  const [demoMode, setDemoMode] = useState(false);
  const [busyTaskId, setBusyTaskId] = useState<string | null>(null);
  const { runStatus, activeRunId, events, risks: inspectionRisks, degraded, dataGaps, startRun, appendEvent, finishRun, failRun, reset, error } = useFarmAgentStore();
  const { data: farms = [], isLoading: farmsLoading } = useQuery({ queryKey: ["farms"], queryFn: getFarms });
  const queryFarmId = Number(searchParams.get("farmId"));
  const linkedFarmId = Number.isInteger(queryFarmId) && farms.some((farm) => farm.id === queryFarmId) ? queryFarmId : null;
  const farmId = selectedFarmId ?? linkedFarmId ?? farms[0]?.id ?? null;
  const selectedFarm = farms.find((farm) => farm.id === farmId) ?? null;
  const { data: proposals = [] } = useQuery({ queryKey: ["farm-agent-proposals", farmId], queryFn: () => listFarmProposals({ farm_id: farmId ?? undefined }), enabled: farmId !== null });
  const { data: tasks = [] } = useQuery({ queryKey: ["farm-agent-tasks", farmId], queryFn: () => listFarmTasks({ farm_id: farmId ?? undefined }), enabled: farmId !== null });
  const { data: timeline } = useQuery({ queryKey: ["farm-agent-timeline", activeRunId], queryFn: () => getFarmRunTimeline(activeRunId ?? ""), enabled: activeRunId !== null && runStatus !== "running" });

  useEffect(() => () => { abortRef.current?.abort(); reset(); }, [reset]);

  const refreshWorkflow = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["farm-agent-proposals", farmId] }),
      queryClient.invalidateQueries({ queryKey: ["farm-agent-tasks", farmId] }),
    ]);
  };

  const inspect = async () => {
    if (farmId === null || runStatus === "running") return;
    abortRef.current?.abort();
    const controller = new AbortController(); abortRef.current = controller; startRun();
    try {
      for await (const event of streamFarmInspection({ farm_id: farmId, ...(demoMode ? { demo_scenario: "rainstorm" as const } : {}) }, controller.signal)) {
        appendEvent(event);
        if (event.type === "proposal_created") await queryClient.invalidateQueries({ queryKey: ["farm-agent-proposals", farmId] });
        if (event.type === "error") throw new Error(event.message || "巡检执行失败");
      }
      finishRun(); await refreshWorkflow();
    } catch (caught) {
      if (caught instanceof DOMException && caught.name === "AbortError") { reset(); return; }
      failRun(caught instanceof Error ? caught.message : "巡检执行失败");
    }
  };

  const approval = useMutation({ mutationFn: ({ proposalId, actions, note }: { proposalId: string; actions: ProposedAction[]; note: string }) => approveFarmProposal(proposalId, { actions, decision_note: note }), onSuccess: async () => { showToast("提案已批准，任务已生成", "success"); await refreshWorkflow(); }, onError: (caught) => showToast(caught instanceof ApiError && caught.status === 409 ? "提案状态已变化，请刷新" : caught instanceof Error ? caught.message : "审批失败", "error") });
  const rejection = useMutation({ mutationFn: ({ proposalId, note }: { proposalId: string; note: string }) => rejectFarmProposal(proposalId, note), onSuccess: async () => { showToast("提案已拒绝", "info"); await refreshWorkflow(); }, onError: (caught) => showToast(caught instanceof ApiError && caught.status === 409 ? "提案状态已变化，请刷新" : "拒绝失败", "error") });

  const runTaskAction = async (taskId: string, action: () => Promise<unknown>, message: string) => { setBusyTaskId(taskId); try { await action(); showToast(message, "success"); await refreshWorkflow(); } catch (caught) { showToast(caught instanceof Error ? caught.message : "任务操作失败", "error"); } finally { setBusyTaskId(null); } };
  const pendingProposals = proposals.filter((proposal) => proposal.status === "pending");

  return <WorkspaceLayout title="AI 农场驾驶舱" icon={Radar} iconColor="text-[#1f6a4b]" description="从风险证据到人工决策，再到现场任务与 AI 复核" fullWidth>
    <div className="relative overflow-hidden rounded-[28px] border border-[#244b3a] bg-[#15392c] px-5 py-5 text-white shadow-[0_24px_70px_-38px_rgba(16,55,42,.9)] sm:px-7">
      <div className="pointer-events-none absolute -right-16 -top-20 h-56 w-56 rounded-full border-[36px] border-white/5" />
      <div className="relative flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between"><div><p className="text-[10px] font-bold uppercase tracking-[0.28em] text-[#9bc9ad]">Agricultural command deck</p><h1 className="mt-2 text-2xl font-semibold tracking-tight sm:text-3xl">让智能体把判断变成可审计的农事行动</h1><p className="mt-2 max-w-2xl text-sm leading-6 text-[#c7ddd0]">每条风险都带证据，每项行动都经过人工批准，每次验收都保留最终决定权。</p></div>
        <div className="flex flex-wrap items-center gap-2"><select aria-label="选择农场" value={farmId ?? ""} onChange={(e) => setSelectedFarmId(Number(e.target.value))} disabled={farms.length === 0} className="min-w-40 rounded-xl border border-white/15 bg-white/10 px-3 py-2.5 text-sm text-white outline-none"><option value="" className="text-slate-900">选择农场</option>{farms.map((farm) => <option key={farm.id} value={farm.id} className="text-slate-900">{farm.name}</option>)}</select>
          <button type="button" aria-pressed={demoMode} onClick={() => setDemoMode((value) => !value)} className={`rounded-xl border px-3 py-2.5 text-xs font-semibold ${demoMode ? "border-[#f5b84b] bg-[#f5b84b] text-[#35250d]" : "border-white/15 bg-white/8 text-[#d7e6da]"}`}><Sparkles className="mr-1.5 inline h-3.5 w-3.5" />{demoMode ? "比赛演示数据" : "真实数据"}</button>
          <button type="button" onClick={() => void inspect()} disabled={farmId === null || runStatus === "running"} className="inline-flex items-center gap-2 rounded-xl bg-[#f5b84b] px-4 py-2.5 text-sm font-bold text-[#33240f] hover:bg-[#ffca69] disabled:opacity-50">{runStatus === "running" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Radar className="h-4 w-4" />}开始 AI 综合巡检</button></div></div>
    </div>
    {farmsLoading ? <div className="py-16 text-center text-sm text-text-muted"><Loader2 className="mx-auto mb-2 h-5 w-5 animate-spin" />加载农场…</div> : farms.length === 0 ? <div className="mt-5 rounded-2xl border border-dashed border-[#b8b09f] bg-[#faf8f1] py-16 text-center"><Tractor className="mx-auto h-8 w-8 text-[#837761]" /><h2 className="mt-3 font-semibold text-[#34453b]">先创建农场，再启动智能巡检</h2><Link to="/workspace/farms" className="mt-4 inline-block rounded-lg bg-[#1f6a4b] px-4 py-2 text-sm font-semibold text-white">前往农场管理</Link></div> : <>
      {error && <div role="alert" className="mt-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">{error}</div>}
      <div className="mt-5 grid gap-5 xl:grid-cols-[minmax(0,.9fr)_minmax(0,1.15fr)_minmax(0,1fr)]">
        <section><div className="mb-3 flex items-end justify-between"><div><p className="text-[10px] font-bold uppercase tracking-[0.22em] text-[#8b785c]">Farm situation</p><h2 className="mt-1 font-semibold text-[#2e4036]">{selectedFarm?.name} · 风险态势</h2></div><CloudRain className="h-5 w-5 text-[#9d6d2e]" /></div><div className="space-y-3">{inspectionRisks.length ? inspectionRisks.map((risk) => <FarmRiskCard key={risk.risk_key} risk={risk} degraded={degraded} />) : proposals.length ? proposals.map((proposal) => <FarmRiskCard key={proposal.proposal_id} risk={proposalRisk(proposal)} />) : <div className="rounded-2xl border border-dashed border-[#d6cebf] bg-[#fbfaf5] px-4 py-12 text-center text-xs text-[#8c8375]">暂无结构化风险，启动巡检后生成证据。</div>}{dataGaps.length > 0 && <div className="rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">数据缺口：{dataGaps.join("；")}</div>}</div></section>
        <AgentRunTimeline events={events.length ? events : timeline?.events ?? []} status={runStatus} />
        <section><div className="mb-3 flex items-end justify-between"><div><p className="text-[10px] font-bold uppercase tracking-[0.22em] text-[#8b785c]">Human decision</p><h2 className="mt-1 font-semibold text-[#2e4036]">待确认行动提案</h2></div><span className="rounded-full bg-amber-100 px-2 py-1 text-xs font-bold text-amber-800">{pendingProposals.length}</span></div><div className="space-y-3">{pendingProposals.map((proposal) => <ActionProposalCard key={proposal.proposal_id} proposal={proposal} busy={approval.isPending || rejection.isPending} onApprove={(actions, note) => approval.mutate({ proposalId: proposal.proposal_id, actions, note })} onReject={(note) => rejection.mutate({ proposalId: proposal.proposal_id, note })} />)}{pendingProposals.length === 0 && <div className="rounded-2xl border border-dashed border-[#d6cebf] bg-[#fbfaf5] px-4 py-12 text-center"><Bot className="mx-auto mb-2 h-6 w-6 text-[#8c8375]" /><p className="text-xs text-[#8c8375]">没有等待人工决策的提案。</p></div>}</div></section>
      </div>
      <div className="mt-6"><FarmTaskBoard tasks={tasks} busyTaskId={busyTaskId} onStart={(taskId) => void runTaskAction(taskId, () => startFarmTask(taskId), "任务已开始")} onSubmit={(taskId, request: TaskSubmitRequest) => void runTaskAction(taskId, () => submitFarmTask(taskId, request), "作业证据已提交")} onComplete={(taskId, note) => void runTaskAction(taskId, () => completeFarmTask(taskId, note), "任务已人工完成")} onReturn={(taskId, note) => void runTaskAction(taskId, () => returnFarmTask(taskId, note), "任务已退回整改")} /></div>
    </>}
  </WorkspaceLayout>;
}
