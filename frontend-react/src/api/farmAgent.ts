import type { ApiResponse } from "../types/api";
import type {
  AgentRunTimeline,
  ApprovalResult,
  FarmActionProposal,
  FarmAgentEvent,
  FarmAgentEventType,
  FarmInspectionRequest,
  ProposalApprovalRequest,
  ProposalFilters,
} from "../types/farmAgent";
import { ApiError, authFetch, authFetchRaw, consumeSSE } from "./client";

const FARM_AGENT_EVENT_TYPES: ReadonlySet<string> = new Set([
  "start",
  "context_loaded",
  "skill_selected",
  "plan",
  "step_start",
  "tool_call",
  "step_complete",
  "replan",
  "proposal_created",
  "report",
  "complete",
  "error",
  "step_token",
  "usage",
  "progress",
]);

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isFarmAgentEventType(value: unknown): value is FarmAgentEventType {
  return typeof value === "string" && FARM_AGENT_EVENT_TYPES.has(value);
}

export function parseFarmAgentEvent(value: Record<string, unknown>): FarmAgentEvent {
  const type = value.type;
  if (
    !isFarmAgentEventType(type) ||
    typeof value.run_id !== "string" ||
    typeof value.stage !== "string"
  ) {
    throw new Error("Farm Agent 返回了无效的 SSE 事件");
  }
  const eventId = typeof value.event_id === "string"
    ? value.event_id
    : type === "error"
      ? `${value.run_id || "stream"}:${value.stage}:error`
      : null;
  if (eventId === null) throw new Error("Farm Agent SSE 事件缺少 event_id");
  return {
    event_id: eventId,
    type,
    run_id: value.run_id,
    stage: value.stage,
    message: typeof value.message === "string" ? value.message : "",
    data: isRecord(value.data) ? value.data : {},
    ts: typeof value.ts === "string" ? value.ts : null,
  };
}

async function requireOk(response: Response): Promise<Response> {
  if (response.ok) return response;
  const message = await response.text().catch(() => "");
  throw new ApiError(response.status, message || `HTTP ${response.status}`);
}

export async function* streamFarmInspection(
  request: FarmInspectionRequest,
  signal?: AbortSignal,
): AsyncGenerator<FarmAgentEvent> {
  const response = await requireOk(
    await authFetchRaw("/farm-agent/inspections/stream", {
      method: "POST",
      body: JSON.stringify(request),
      signal,
    }),
  );
  for await (const event of consumeSSE(response)) {
    yield parseFarmAgentEvent(event);
  }
}

export async function getFarmRunTimeline(runId: string): Promise<AgentRunTimeline> {
  const response = await authFetch<ApiResponse<AgentRunTimeline>>(
    `/farm-agent/runs/${encodeURIComponent(runId)}/timeline`,
  );
  return response.data;
}

export async function getLatestInspectionRun(
  farmId?: number,
): Promise<AgentRunTimeline | null> {
  const query = farmId === undefined ? "" : `?farm_id=${encodeURIComponent(String(farmId))}`;
  const response = await authFetch<ApiResponse<AgentRunTimeline | null>>(
    `/farm-agent/runs/latest${query}`,
  );
  return response.data;
}

export async function listFarmProposals(
  filters: ProposalFilters = {},
): Promise<FarmActionProposal[]> {
  const params = new URLSearchParams();
  if (filters.farm_id !== undefined) params.set("farm_id", String(filters.farm_id));
  if (filters.status !== undefined) params.set("status", filters.status);
  const query = params.size > 0 ? `?${params.toString()}` : "";
  const response = await authFetch<ApiResponse<FarmActionProposal[]>>(
    `/farm-agent/proposals${query}`,
  );
  return response.data;
}

export async function approveFarmProposal(
  proposalId: string,
  body: ProposalApprovalRequest,
): Promise<ApprovalResult> {
  const response = await authFetch<ApiResponse<ApprovalResult>>(
    `/farm-agent/proposals/${encodeURIComponent(proposalId)}/approve`,
    { method: "POST", body: JSON.stringify(body) },
  );
  return response.data;
}

export async function rejectFarmProposal(
  proposalId: string,
  decisionNote: string,
): Promise<FarmActionProposal> {
  const response = await authFetch<ApiResponse<FarmActionProposal>>(
    `/farm-agent/proposals/${encodeURIComponent(proposalId)}/reject`,
    { method: "POST", body: JSON.stringify({ decision_note: decisionNote }) },
  );
  return response.data;
}
