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

export type DemoScenario =
  | "rainstorm"
  | "pest_outbreak"
  | "nutrient_deficiency"
  | "drought";

export interface FarmInspectionRequest {
  farm_id: number;
  objective?: string;
  demo_scenario?: DemoScenario | null;
  inject_scenario?: boolean;
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

// ==================== B9 比赛演示感知/事件/茬次契约 ====================

export interface ScenarioMeta {
  scenario_id: string;
  label: string;
  description: string;
  weather_summary: string;
  field_count: number;
  sensor_count: number;
}

export interface InjectionReport {
  scenario_id: string;
  farm_id: number;
  created_sensors: number;
  skipped_sensors: number;
  created_seasons: number;
  updated_seasons: number;
  fields_covered: string[];
}

export interface SensorReading {
  id: number;
  field_id: number;
  sensor_type: string;
  value_float: number | null;
  value: Record<string, unknown>;
  unit: string;
  observed_at: string;
  source: string;
  scenario_id: string | null;
  note: string;
}

export interface FarmEvent {
  id: number;
  field_id: number;
  season_id: number | null;
  event_type: string;
  event_time: string;
  operator: string;
  inputs: unknown[];
  source: string;
  related_task_id: string | null;
  note: string;
}

export interface CropSeason {
  id: number;
  field_id: number;
  crop_name: string;
  variety: string;
  season_code: string;
  start_date: string;
  expected_harvest: string | null;
  current_stage: string;
  area_mu: number;
  target_yield: string;
  status: string;
  note: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface SensorFilters {
  farm_id: number;
  field_id?: number;
  sensor_type?: string;
  days?: number;
}

export interface EventFilters {
  farm_id: number;
  field_id?: number;
  days?: number;
}

export interface SeasonFilters {
  farm_id: number;
  field_id?: number;
  status?: string;
}
