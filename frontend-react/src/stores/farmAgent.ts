import { create } from "zustand";
import type {
  FarmAgentEvent,
  FarmAgentRunStatus,
  FarmRisk,
} from "../types/farmAgent";

interface FarmAgentState {
  runStatus: FarmAgentRunStatus;
  activeRunId: string | null;
  events: FarmAgentEvent[];
  risks: FarmRisk[];
  proposalIds: string[];
  report: string;
  error: string | null;
  startRun: () => void;
  appendEvent: (event: FarmAgentEvent) => void;
  finishRun: () => void;
  failRun: (error: string) => void;
  reset: () => void;
}

const initialState = {
  runStatus: "idle" as const,
  activeRunId: null,
  events: [],
  risks: [],
  proposalIds: [],
  report: "",
  error: null,
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function eventProposalIds(event: FarmAgentEvent): string[] {
  const proposalId = event.data.proposal_id;
  const proposalIds = event.data.proposal_ids;
  const outcome = isRecord(event.data.outcome) ? event.data.outcome : {};
  const outcomeProposalIds = outcome.proposal_ids;
  return [
    ...(typeof proposalId === "string" ? [proposalId] : []),
    ...(Array.isArray(proposalIds)
      ? proposalIds.filter((value): value is string => typeof value === "string")
      : []),
    ...(Array.isArray(outcomeProposalIds)
      ? outcomeProposalIds.filter((value): value is string => typeof value === "string")
      : []),
  ];
}

function eventRisks(event: FarmAgentEvent): FarmRisk[] {
  const risks = event.data.risks;
  if (!Array.isArray(risks)) return [];
  return risks.filter((risk): risk is FarmRisk => {
    if (!isRecord(risk)) return false;
    return (
      typeof risk.risk_key === "string" &&
      typeof risk.confidence === "number" &&
      Array.isArray(risk.evidence) &&
      Array.isArray(risk.suggested_actions)
    );
  });
}

export const useFarmAgentStore = create<FarmAgentState>((set) => ({
  ...initialState,

  startRun: () => set({ ...initialState, runStatus: "running" }),

  appendEvent: (event) =>
    set((state) => {
      if (state.events.some((item) => item.event_id === event.event_id)) return state;
      const newProposalIds = eventProposalIds(event);
      const report = event.data.report;
      return {
        events: [...state.events, event],
        activeRunId: event.run_id || state.activeRunId,
        risks: [...state.risks, ...eventRisks(event)],
        proposalIds: [...new Set([...state.proposalIds, ...newProposalIds])],
        report: typeof report === "string" ? report : state.report,
      };
    }),

  finishRun: () => set({ runStatus: "completed", error: null }),
  failRun: (error) => set({ runStatus: "failed", error }),
  reset: () => set(initialState),
}));
