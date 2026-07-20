import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ChevronDown,
  ChevronUp,
  History,
  LayoutList,
  Loader2,
  Radar,
  Sparkles,
  Sprout,
  Syringe,
  Tractor,
} from "lucide-react";
import { getFarms } from "../api/farms";
import { ApiError } from "../api/client";
import {
  approveFarmProposal,
  getFarmRunTimeline,
  injectFarmScenario,
  listFarmProposals,
  listFarmScenarios,
  rejectFarmProposal,
  streamFarmInspection,
} from "../api/farmAgent";
import {
  completeFarmTask,
  listFarmTasks,
  returnFarmTask,
  startFarmTask,
  submitFarmTask,
} from "../api/farmTasks";
import { useFarmAgentStore } from "../stores/farmAgent";
import { useUIStore } from "../stores/ui";
import type {
  DemoScenario,
  ProposedAction,
  TaskSubmitRequest,
} from "../types/farmAgent";
import WorkspaceLayout from "../components/layout/WorkspaceLayout";
import AgentRunTimeline from "../components/farm-agent/AgentRunTimeline";
import CurrentInsightCard, {
  EmptyInsight,
} from "../components/farm-agent/CurrentInsightCard";
import FarmTaskBoard from "../components/farm-agent/FarmTaskBoard";
import SensorPanel from "../components/farm-agent/SensorPanel";
import FarmEventTimeline from "../components/farm-agent/FarmEventTimeline";
import InspectionStepper from "../components/farm-agent/InspectionStepper";

const SEVERITY_ORDER: Record<string, number> = {
  critical: 0,
  high: 1,
  medium: 2,
  low: 3,
};

export default function FarmAgent() {
  const [searchParams] = useSearchParams();
  const queryClient = useQueryClient();
  const showToast = useUIStore((state) => state.showToast);
  const abortRef = useRef<AbortController | null>(null);
  const [selectedFarmId, setSelectedFarmId] = useState<number | null>(null);
  const [selectedScenario, setSelectedScenario] = useState<DemoScenario | null>(
    null,
  );
  const [perceptionRefreshKey, setPerceptionRefreshKey] = useState(0);
  const [busyTaskId, setBusyTaskId] = useState<string | null>(null);
  const [expandedPanels, setExpandedPanels] = useState<Set<string>>(new Set());
  const {
    runStatus,
    activeRunId,
    events,
    risks: inspectionRisks,
    dataGaps,
    startRun,
    appendEvent,
    finishRun,
    failRun,
    reset,
    error,
  } = useFarmAgentStore();

  const { data: farms = [], isLoading: farmsLoading } = useQuery({
    queryKey: ["farms"],
    queryFn: getFarms,
  });
  const { data: scenarios = [] } = useQuery({
    queryKey: ["farm-agent-scenarios"],
    queryFn: listFarmScenarios,
  });

  const queryFarmId = Number(searchParams.get("farmId"));
  const linkedFarmId =
    Number.isInteger(queryFarmId) &&
    farms.some((farm) => farm.id === queryFarmId)
      ? queryFarmId
      : null;
  const farmId = selectedFarmId ?? linkedFarmId ?? farms[0]?.id ?? null;

  const { data: proposals = [] } = useQuery({
    queryKey: ["farm-agent-proposals", farmId],
    queryFn: () => listFarmProposals({ farm_id: farmId ?? undefined }),
    enabled: farmId !== null,
  });
  const { data: tasks = [] } = useQuery({
    queryKey: ["farm-agent-tasks", farmId],
    queryFn: () => listFarmTasks({ farm_id: farmId ?? undefined }),
    enabled: farmId !== null,
  });
  const { data: timeline } = useQuery({
    queryKey: ["farm-agent-timeline", activeRunId],
    queryFn: () => getFarmRunTimeline(activeRunId ?? ""),
    enabled: activeRunId !== null && runStatus !== "running",
  });

  useEffect(
    () => () => {
      abortRef.current?.abort();
      reset();
    },
    [reset],
  );

  const refreshWorkflow = async () => {
    await Promise.all([
      queryClient.invalidateQueries({
        queryKey: ["farm-agent-proposals", farmId],
      }),
      queryClient.invalidateQueries({
        queryKey: ["farm-agent-tasks", farmId],
      }),
      queryClient.invalidateQueries({
        queryKey: ["farm-agent-sensors", farmId],
      }),
      queryClient.invalidateQueries({
        queryKey: ["farm-agent-events", farmId],
      }),
    ]);
  };

  const injectMutation = useMutation({
    mutationFn: ({
      scenarioId,
      targetFarmId,
    }: {
      scenarioId: DemoScenario;
      targetFarmId: number;
    }) => injectFarmScenario(scenarioId, targetFarmId),
    onSuccess: async (report) => {
      setPerceptionRefreshKey((key) => key + 1);
      showToast(
        `场景 ${report.scenario_id} 注入完成：新增 ${report.created_sensors} 条感知、${report.created_seasons} 个茬次，覆盖地块 ${report.fields_covered.join("、")}`,
        "success",
      );
      await refreshWorkflow();
    },
    onError: (caught) =>
      showToast(
        caught instanceof ApiError && caught.status === 409
          ? "地块与场景不匹配，请确认农场已包含所需地块"
          : caught instanceof Error
            ? caught.message
            : "场景注入失败",
        "error",
      ),
  });

  const inspect = async () => {
    if (farmId === null || runStatus === "running") return;
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    startRun();
    try {
      for await (const event of streamFarmInspection(
        {
          farm_id: farmId,
          ...(selectedScenario ? { demo_scenario: selectedScenario } : {}),
        },
        controller.signal,
      )) {
        appendEvent(event);
        if (event.type === "proposal_created")
          await queryClient.invalidateQueries({
            queryKey: ["farm-agent-proposals", farmId],
          });
        if (event.type === "error") throw new Error(event.message || "巡检执行失败");
      }
      finishRun();
      await refreshWorkflow();
    } catch (caught) {
      if (caught instanceof DOMException && caught.name === "AbortError") {
        reset();
        return;
      }
      failRun(
        caught instanceof Error ? caught.message : "巡检执行失败",
      );
    }
  };

  const approval = useMutation({
    mutationFn: ({
      proposalId,
      actions,
      note,
    }: {
      proposalId: string;
      actions: ProposedAction[];
      note: string;
    }) => approveFarmProposal(proposalId, { actions, decision_note: note }),
    onSuccess: async () => {
      showToast("提案已批准，任务已生成", "success");
      await refreshWorkflow();
    },
    onError: (caught) =>
      showToast(
        caught instanceof ApiError && caught.status === 409
          ? "提案状态已变化，请刷新"
          : caught instanceof Error
            ? caught.message
            : "审批失败",
        "error",
      ),
  });
  const rejection = useMutation({
    mutationFn: ({ proposalId, note }: { proposalId: string; note: string }) =>
      rejectFarmProposal(proposalId, note),
    onSuccess: async () => {
      showToast("提案已拒绝", "info");
      await refreshWorkflow();
    },
    onError: (caught) =>
      showToast(
        caught instanceof ApiError && caught.status === 409
          ? "提案状态已变化，请刷新"
          : "拒绝失败",
        "error",
      ),
  });

  const runTaskAction = async (
    taskId: string,
    action: () => Promise<unknown>,
    message: string,
  ) => {
    setBusyTaskId(taskId);
    try {
      await action();
      showToast(message, "success");
      await refreshWorkflow();
    } catch (caught) {
      showToast(
        caught instanceof Error ? caught.message : "任务操作失败",
        "error",
      );
    } finally {
      setBusyTaskId(null);
    }
  };

  const pendingProposals = proposals.filter(
    (proposal) => proposal.status === "pending",
  );
  const injectDisabled =
    farmId === null || selectedScenario === null || injectMutation.isPending;

  const activeStep = useMemo(() => {
    if (
      tasks.some((task) =>
        ["in_progress", "submitted", "completed"].includes(task.status),
      )
    )
      return 4;
    if (pendingProposals.length > 0) return 3;
    if (
      inspectionRisks.length > 0 ||
      proposals.length > 0 ||
      runStatus === "completed"
    )
      return 2;
    if (runStatus === "running") return 1;
    return 0;
  }, [tasks, pendingProposals, inspectionRisks, proposals, runStatus]);

  const currentInsight = useMemo(() => {
    if (pendingProposals.length > 0) {
      return { type: "proposal" as const, data: pendingProposals[0] };
    }
    if (inspectionRisks.length > 0) {
      const sorted = [...inspectionRisks].sort(
        (a, b) =>
          (SEVERITY_ORDER[a.severity] ?? 99) -
          (SEVERITY_ORDER[b.severity] ?? 99),
      );
      return { type: "risk" as const, data: sorted[0] };
    }
    return null;
  }, [pendingProposals, inspectionRisks]);

  const togglePanel = (id: string) => {
    setExpandedPanels((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const activeTaskCount = tasks.filter((task) =>
    ["in_progress", "submitted"].includes(task.status),
  ).length;
  const pendingTaskCount = tasks.filter((task) =>
    ["pending", "returned"].includes(task.status),
  ).length;

  useEffect(() => {
    if (pendingTaskCount > 0) {
      setExpandedPanels((prev) => new Set(prev).add("tasks"));
    }
  }, [pendingTaskCount]);

  const scenarioMeta = useMemo(() => {
    if (!selectedScenario) return null;
    return scenarios.find((s) => s.scenario_id.startsWith(selectedScenario));
  }, [selectedScenario, scenarios]);

  return (
    <WorkspaceLayout
      title="AI 农场驾驶舱"
      icon={Radar}
      iconColor="text-[#1f6a4b]"
      description="从风险证据到人工决策，再到现场任务与 AI 复核"
      fullWidth
    >
      {farmsLoading ? (
        <div className="py-16 text-center text-sm text-text-muted">
          <Loader2 className="mx-auto mb-2 h-5 w-5 animate-spin" />
          加载农场…
        </div>
      ) : farms.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-[#b8b09f] bg-[#faf8f1] py-16 text-center">
          <Tractor className="mx-auto h-8 w-8 text-[#837761]" />
          <h2 className="mt-3 font-semibold text-[#34453b]">
            先创建农场，再启动智能巡检
          </h2>
          <Link
            to="/workspace/farms"
            className="mt-4 inline-block rounded-lg bg-[#1f6a4b] px-4 py-2 text-sm font-semibold text-white"
          >
            前往农场管理
          </Link>
        </div>
      ) : (
        <div className="space-y-5">
          {/* 步骤引导 + 控制 */}
          <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
              <InspectionStepper activeStep={activeStep} />
              <div className="flex flex-wrap items-center gap-2">
                <select
                  aria-label="选择农场"
                  value={farmId ?? ""}
                  onChange={(e) => setSelectedFarmId(Number(e.target.value))}
                  disabled={farms.length === 0}
                  className="min-w-36 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 outline-none focus:border-[#1f6a4b]"
                >
                  <option value="">选择农场</option>
                  {farms.map((farm) => (
                    <option key={farm.id} value={farm.id}>
                      {farm.name}
                    </option>
                  ))}
                </select>
                <select
                  aria-label="比赛演示场景"
                  value={selectedScenario ?? ""}
                  onChange={(e) =>
                    setSelectedScenario(
                      (e.target.value || null) as DemoScenario | null,
                    )
                  }
                  className="min-w-32 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 outline-none focus:border-[#1f6a4b]"
                >
                  <option value="">真实数据</option>
                  {scenarios.map((scenario) => (
                    <option
                      key={scenario.scenario_id}
                      value={scenario.scenario_id}
                    >
                      {scenario.label}
                    </option>
                  ))}
                </select>
                <button
                  type="button"
                  onClick={() =>
                    selectedScenario &&
                    farmId !== null &&
                    injectMutation.mutate({
                      scenarioId: selectedScenario,
                      targetFarmId: farmId,
                    })
                  }
                  disabled={injectDisabled}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-50 disabled:opacity-50"
                >
                  {injectMutation.isPending ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <Syringe className="h-3.5 w-3.5" />
                  )}
                  注入感知
                </button>
                <button
                  type="button"
                  onClick={() => void inspect()}
                  disabled={farmId === null || runStatus === "running"}
                  className="inline-flex items-center gap-2 rounded-lg bg-[#1f6a4b] px-4 py-2 text-sm font-bold text-white hover:bg-[#16533a] disabled:opacity-50"
                >
                  {runStatus === "running" ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Radar className="h-4 w-4" />
                  )}
                  开始 AI 综合巡检
                </button>
              </div>
            </div>
          </div>

          {error && (
            <div
              role="alert"
              className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800"
            >
              {error}
            </div>
          )}

          {scenarioMeta && (
            <div className="flex items-start gap-2 rounded-xl border border-amber-200/60 bg-amber-50 px-4 py-3 text-xs text-amber-900">
              <Sparkles className="mt-0.5 h-4 w-4 shrink-0 text-amber-600" />
              <div className="min-w-0">
                <p className="font-semibold">
                  比赛演示场景：{scenarioMeta.label}
                </p>
                <p className="mt-0.5 leading-5">{scenarioMeta.description}</p>
                <p className="mt-0.5 text-[10px] text-amber-700/70">
                  {scenarioMeta.weather_summary} · {scenarioMeta.field_count}{" "}
                  个地块 · {scenarioMeta.sensor_count} 条感知
                </p>
              </div>
            </div>
          )}

          {/* 主内容：Agent 轨迹 + 当前洞察 */}
          <div className="grid min-h-[28rem] gap-5 lg:grid-cols-[1.45fr_0.55fr]">
            <AgentRunTimeline
              events={events.length ? events : timeline?.events ?? []}
              status={runStatus}
              riskCount={inspectionRisks.length}
              proposalCount={proposals.length}
            />
            <div className="flex h-full min-h-0 flex-col gap-4">
              {currentInsight ? (
                currentInsight.type === "proposal" ? (
                  <CurrentInsightCard
                    type="proposal"
                    data={currentInsight.data}
                    busy={approval.isPending || rejection.isPending}
                    onApprove={(actions, note) =>
                      approval.mutate({
                        proposalId: currentInsight.data.proposal_id,
                        actions,
                        note,
                      })
                    }
                    onReject={(note) =>
                      rejection.mutate({
                        proposalId: currentInsight.data.proposal_id,
                        note,
                      })
                    }
                  />
                ) : (
                  <CurrentInsightCard type="risk" data={currentInsight.data} />
                )
              ) : (
                <EmptyInsight />
              )}
              {dataGaps.length > 0 && (
                <div className="rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
                  数据缺口：{dataGaps.join("；")}
                </div>
              )}
            </div>
          </div>

          {/* 可折叠详情区 */}
          <div className="rounded-2xl border border-slate-200 bg-white shadow-sm">
            <AccordionItem
              id="sensors"
              title="感知读数"
              subtitle={`近 7 天数据`}
              icon={Sprout}
              expanded={expandedPanels}
              onToggle={togglePanel}
            >
              <SensorPanel
                farmId={farmId}
                days={7}
                refreshKey={perceptionRefreshKey}
                embedded
              />
            </AccordionItem>
            <AccordionItem
              id="events"
              title="事件流"
              subtitle={`近 14 天记录`}
              icon={History}
              expanded={expandedPanels}
              onToggle={togglePanel}
            >
              <FarmEventTimeline
                farmId={farmId}
                days={14}
                refreshKey={perceptionRefreshKey}
                embedded
              />
            </AccordionItem>
            <AccordionItem
              id="tasks"
              title="农事任务闭环"
              subtitle={`${tasks.length} 项任务`}
              icon={LayoutList}
              badge={activeTaskCount > 0 ? activeTaskCount : undefined}
              pulse={activeTaskCount > 0}
              expanded={expandedPanels}
              onToggle={togglePanel}
            >
              <FarmTaskBoard
                tasks={tasks}
                busyTaskId={busyTaskId}
                onStart={(taskId) =>
                  void runTaskAction(
                    taskId,
                    () => startFarmTask(taskId),
                    "任务已开始",
                  )
                }
                onSubmit={(taskId, request: TaskSubmitRequest) =>
                  void runTaskAction(
                    taskId,
                    () => submitFarmTask(taskId, request),
                    "作业证据已提交",
                  )
                }
                onComplete={(taskId, note) =>
                  void runTaskAction(
                    taskId,
                    () => completeFarmTask(taskId, note),
                    "任务已人工完成",
                  )
                }
                onReturn={(taskId, note) =>
                  void runTaskAction(
                    taskId,
                    () => returnFarmTask(taskId, note),
                    "任务已退回整改",
                  )
                }
              />
            </AccordionItem>
          </div>
        </div>
      )}
    </WorkspaceLayout>
  );
}

function AccordionItem({
  id,
  title,
  subtitle,
  icon: Icon,
  badge,
  pulse,
  expanded,
  onToggle,
  children,
}: {
  id: string;
  title: string;
  subtitle: string;
  icon: React.ElementType;
  badge?: number;
  pulse?: boolean;
  expanded: Set<string>;
  onToggle: (id: string) => void;
  children: React.ReactNode;
}) {
  const isExpanded = expanded.has(id);
  return (
    <div className="border-b border-slate-100 last:border-b-0">
      <button
        type="button"
        onClick={() => onToggle(id)}
        className="flex w-full items-center justify-between px-5 py-3.5 text-left transition-colors hover:bg-slate-50"
      >
        <div className="flex items-center gap-3">
          <span className="grid h-8 w-8 place-items-center rounded-lg bg-emerald-50 text-emerald-600">
            <Icon className="h-4 w-4" />
          </span>
          <div className="flex items-center gap-2">
            <span className="text-sm font-semibold text-slate-700">
              {title}
            </span>
            {badge !== undefined && badge > 0 && (
              <span className="rounded-full bg-red-100 px-2 py-0.5 text-xs font-bold text-red-700">
                {badge}
              </span>
            )}
            {pulse && (
              <span className="relative flex h-2 w-2">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-red-400 opacity-75" />
                <span className="relative inline-flex h-2 w-2 rounded-full bg-red-500" />
              </span>
            )}
          </div>
          <span className="text-xs text-slate-400">{subtitle}</span>
        </div>
        {isExpanded ? (
          <ChevronUp className="h-4 w-4 text-slate-400" />
        ) : (
          <ChevronDown className="h-4 w-4 text-slate-400" />
        )}
      </button>
      {isExpanded && <div className="px-5 pb-5">{children}</div>}
    </div>
  );
}
