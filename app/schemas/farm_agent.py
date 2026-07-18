"""Farm Agent 巡检、提案、任务和运行时间线数据契约."""

from datetime import datetime
from typing import Any, Literal
from urllib.parse import urlsplit

from pydantic import (
    AnyHttpUrl,
    BaseModel,
    ConfigDict,
    Field,
    TypeAdapter,
    ValidationError,
    field_validator,
    model_validator,
)

from app.schemas.trajectory import TrajectoryFileInfo

_HTTP_URL_ADAPTER = TypeAdapter(AnyHttpUrl)

Severity = Literal["low", "medium", "high", "critical"]
ProposalStatus = Literal["pending", "approved", "rejected"]
TaskStatus = Literal[
    "pending",
    "in_progress",
    "submitted",
    "returned",
    "completed",
    "cancelled",
]
VerificationVerdict = Literal["pass", "needs_evidence", "rework", "manual_review"]
EvidenceFactKind = Literal["measured", "rule", "inference"]
TaskPriority = Literal["normal", "high", "urgent"]
TaskExecutionAction = Literal["start", "submit", "complete", "return", "cancel"]
FarmAgentEventType = Literal[
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
]


class FarmEvidence(BaseModel):
    """支撑提案判断的可追溯证据."""

    source_type: str = Field(..., min_length=1, max_length=64)
    source_id: str = Field(..., min_length=1, max_length=128)
    summary: str = Field(..., min_length=1, max_length=1000)
    observed_at: datetime
    fact_kind: EvidenceFactKind
    payload: dict[str, Any] = Field(default_factory=dict)


class ProposedAction(BaseModel):
    """提案内可由人工调整的结构化行动."""

    action_key: str = Field(..., min_length=1, max_length=128)
    title: str = Field(..., min_length=1, max_length=256)
    task_type: str = Field(..., min_length=1, max_length=64)
    instructions: str = Field(..., min_length=1)
    priority: TaskPriority = "normal"
    field_id: int | None = Field(default=None, gt=0)
    assignee_name: str = Field(default="", max_length=128)
    due_at: datetime | None = None
    acceptance_criteria: list[str] = Field(default_factory=list)


class ProposalDraft(BaseModel):
    """Agent 生成并经校验后才能持久化的提案草稿."""

    risk_key: str = Field(..., min_length=1, max_length=256)
    title: str = Field(..., min_length=1, max_length=256)
    severity: Severity
    summary: str = Field(..., min_length=1)
    confidence: float = Field(..., ge=0.0, le=1.0)
    evidence: list[FarmEvidence] = Field(..., min_length=1)
    actions: list[ProposedAction] = Field(..., min_length=1)

    @model_validator(mode="after")
    def require_observed_evidence_for_high_confidence(self) -> "ProposalDraft":
        if self.confidence >= 0.8 and not any(
            item.fact_kind in {"measured", "rule"} for item in self.evidence
        ):
            raise ValueError("高置信度提案必须包含 measured 或 rule 证据")
        return self


class ProposalResponse(BaseModel):
    """已持久化行动提案."""

    proposal_id: str
    farm_id: int
    created_by: int
    run_id: str
    risk_fingerprint: str
    title: str
    severity: Severity
    summary: str
    confidence: float
    evidence: list[FarmEvidence]
    actions: list[ProposedAction]
    status: ProposalStatus
    decision_note: str = ""
    created_at: datetime
    decided_at: datetime | None = None

    model_config = {"from_attributes": True}


class FarmInspectionRequest(BaseModel):
    """启动一次 Farm Agent 综合巡检."""

    farm_id: int = Field(..., gt=0)
    objective: str = Field(default="请对当前农场执行综合巡检", min_length=1)
    demo_scenario: Literal["rainstorm"] | None = None


class FarmAgentEvent(BaseModel):
    """Farm Agent SSE 事件."""

    event_id: str
    type: FarmAgentEventType
    run_id: str
    stage: str = ""
    message: str = ""
    data: dict[str, Any] = Field(default_factory=dict)
    ts: datetime | None = None


class ProposalApprovalRequest(BaseModel):
    """人工批准提案时最终确认的行动列表."""

    actions: list[ProposedAction] = Field(..., min_length=1)
    decision_note: str

    @model_validator(mode="after")
    def require_unique_action_keys(self) -> "ProposalApprovalRequest":
        action_keys = [action.action_key for action in self.actions]
        if len(action_keys) != len(set(action_keys)):
            raise ValueError("审批 actions 的 action_key 不得重复")
        return self


class ProposalRejectRequest(BaseModel):
    """人工拒绝提案的说明."""

    decision_note: str


class TaskExecutionAuditEntry(BaseModel):
    """一次显式人工任务状态转换的审计记录."""

    actor: Literal["human"]
    action: TaskExecutionAction
    note: str
    timestamp: datetime

    model_config = ConfigDict(extra="forbid")


class TaskSubmissionEvidence(BaseModel):
    """作业人员提交并持久化到 execution JSON 的证据字段."""

    note: str = ""
    trajectory_file_ids: list[int] = Field(default_factory=list)
    attachment_urls: list[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")

    @field_validator("attachment_urls")
    @classmethod
    def require_http_attachment_urls(cls, urls: list[str]) -> list[str]:
        """附件只接受带主机名的 HTTP(S) URL."""

        for url in urls:
            try:
                parsed = urlsplit(url)
                if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
                    raise ValueError("附件 URL 必须使用 HTTP(S) 且包含主机名")
                _HTTP_URL_ADAPTER.validate_python(url)
            except (ValidationError, ValueError) as exc:
                raise ValueError("附件 URL 格式无效") from exc
        return urls


class TaskExecution(TaskSubmissionEvidence):
    """FarmTask.execution_json 的完整类型化结构."""

    audit: list[TaskExecutionAuditEntry] = Field(default_factory=list)
    completion_note: str | None = None
    return_reason: str | None = None
    cancellation_reason: str | None = None


class TaskSubmitRequest(TaskSubmissionEvidence):
    """作业人员提交的任务执行证据."""


class TaskVerificationDraft(BaseModel):
    """AI 对已提交任务生成、等待人工决定的复核草稿."""

    verdict: VerificationVerdict
    note: str = Field(..., min_length=1)
    evidence_refs: list[str] = Field(default_factory=list)


class TaskDecisionRequest(BaseModel):
    """人工完成或退回任务时的说明."""

    note: str


class TaskResponse(BaseModel):
    """农场执行任务."""

    task_id: str
    proposal_id: str | None = None
    action_key: str | None = None
    farm_id: int
    field_id: int | None = None
    assignee_name: str = ""
    title: str
    task_type: str
    instructions: str
    acceptance_criteria: list[str]
    priority: TaskPriority
    status: TaskStatus
    due_at: datetime | None = None
    execution: TaskExecution
    agent_verdict: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TaskEvidenceBundle(BaseModel):
    """供任务复核使用的目标、执行记录和关联证据."""

    task_id: str
    farm_id: int
    field_id: int | None = None
    title: str
    instructions: str
    acceptance_criteria: list[str]
    status: TaskStatus
    execution: TaskExecution
    trajectory_files: list[TrajectoryFileInfo] = Field(default_factory=list)
    attachment_urls: list[str] = Field(default_factory=list)


class AgentRunTimelineResponse(BaseModel):
    """由真实 AgentRun 转换记录组装的可观测时间线."""

    run_id: str
    farm_id: int | None = None
    run_type: str | None = None
    status: str | None = None
    events: list[FarmAgentEvent] = Field(default_factory=list)
    total_steps: int = 0
    total_tool_calls: int = 0
    total_tokens: int = 0
    total_ms: int = 0
    context_snapshot: dict[str, Any] = Field(default_factory=dict)
    outcome: dict[str, Any] = Field(default_factory=dict)
    proposal_ids: list[str] = Field(default_factory=list)
    created_at: datetime | None = None
