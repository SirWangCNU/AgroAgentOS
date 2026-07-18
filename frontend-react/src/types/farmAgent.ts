export type Severity = "low" | "medium" | "high" | "critical";
export type ProposalStatus = "pending" | "approved" | "rejected";
export type TaskStatus =
  | "pending"
  | "in_progress"
  | "submitted"
  | "returned"
  | "completed"
  | "cancelled";
export type TaskPriority = "normal" | "high" | "urgent";
export type EvidenceFactKind = "measured" | "rule" | "inference";
export type VerificationVerdict =
  | "pass"
  | "needs_evidence"
  | "rework"
  | "manual_review";
export type FarmAgentEventType =
  | "start"
  | "context_loaded"
  | "skill_selected"
  | "plan"
  | "step_start"
  | "tool_call"
  | "step_complete"
  | "replan"
  | "proposal_created"
  | "report"
  | "complete"
  | "error"
  | "step_token"
  | "usage"
  | "progress";
export type FarmAgentRunStatus = "idle" | "running" | "completed" | "failed";
export type AgentRunStatus = "running" | "completed" | "failed" | "cancelled";

export interface FarmEvidence {
  source_type: string;
  source_id: string;
  summary: string;
  observed_at: string | null;
  fact_kind: EvidenceFactKind;
  payload: Record<string, unknown>;
}

export interface FarmRisk {
  risk_key: string;
  severity: Severity;
  confidence: number;
  evidence: FarmEvidence[];
  suggested_actions: string[];
}

export interface ProposedAction {
  action_key: string;
  title: string;
  task_type: string;
  instructions: string;
  priority: TaskPriority;
  field_id: number | null;
  assignee_name: string;
  due_at: string | null;
  acceptance_criteria: string[];
}

export interface FarmActionProposal {
  proposal_id: string;
  farm_id: number;
  created_by: number;
  run_id: string;
  risk_fingerprint: string;
  title: string;
  severity: Severity;
  summary: string;
  confidence: number;
  evidence: FarmEvidence[];
  actions: ProposedAction[];
  status: ProposalStatus;
  decision_note: string;
  created_at: string | null;
  decided_at: string | null;
}

export interface TaskExecutionAuditEntry {
  actor: "human";
  action: "start" | "submit" | "complete" | "return" | "cancel";
  note: string;
  timestamp: string | null;
}

export interface TaskExecution {
  note: string;
  trajectory_file_ids: number[];
  attachment_urls: string[];
  audit: TaskExecutionAuditEntry[];
  completion_note: string | null;
  return_reason: string | null;
  cancellation_reason: string | null;
}

export interface TaskVerificationDraft {
  verdict: VerificationVerdict;
  note: string;
  evidence_refs: string[];
}

export interface FarmTask {
  task_id: string;
  proposal_id: string | null;
  action_key: string | null;
  farm_id: number;
  field_id: number | null;
  assignee_name: string;
  title: string;
  task_type: string;
  instructions: string;
  acceptance_criteria: string[];
  priority: TaskPriority;
  status: TaskStatus;
  due_at: string | null;
  execution: TaskExecution;
  agent_verdict: Partial<TaskVerificationDraft> & Record<string, unknown>;
  created_at: string | null;
  updated_at: string | null;
}

export interface FarmAgentEvent {
  event_id: string;
  type: FarmAgentEventType;
  run_id: string;
  stage: string;
  message: string;
  data: Record<string, unknown>;
  ts: string | null;
}

export interface AgentRunTimeline {
  run_id: string;
  farm_id: number | null;
  run_type: "inspection" | "task_verification" | null;
  status: AgentRunStatus | null;
  events: FarmAgentEvent[];
  total_steps: number;
  total_tool_calls: number;
  total_tokens: number;
  total_ms: number;
  context_snapshot: Record<string, unknown>;
  outcome: Record<string, unknown>;
  proposal_ids: string[];
  created_at: string | null;
}

export interface FarmInspectionRequest {
  farm_id: number;
  objective?: string;
  demo_scenario?: "rainstorm" | null;
}

export interface ProposalFilters {
  farm_id?: number;
  status?: ProposalStatus;
}

export interface ProposalApprovalRequest {
  actions: ProposedAction[];
  decision_note: string;
}

export interface ApprovalResult {
  proposal: FarmActionProposal;
  tasks: FarmTask[];
  task_ids: string[];
}

export interface TaskFilters {
  farm_id?: number;
  status?: TaskStatus;
}

export interface TaskSubmitRequest {
  note: string;
  trajectory_file_ids: number[];
  attachment_urls: string[];
}
