"""AIOps 多智能体接口的数据模型."""

from typing import Any, Dict, Literal

from pydantic import BaseModel, Field


class DiagnosisRequest(BaseModel):
    """AIOps 诊断请求."""

    session_id: str = Field(default="default", description="会话 ID")
    query: str = Field(
        ...,
        description="告警内容 / 故障现象 / 运维问题",
        min_length=1,
        max_length=4000,
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "session_id": "diag-001",
                "query": "数据库 CPU 使用率持续 100%, 已经 30 分钟, 业务受影响",
            }
        }
    }


# ============================================================
# SSE 事件 schema (仅用于 OpenAPI 文档示例, 实际 SSE 用 JSON 字符串)
# ============================================================
EventType = Literal[
    "start",           # 流程启动
    "skill_selected",  # SkillRouter 选定 Skill
    "plan",            # Planner 完成, 给出初始计划
    "step_start",      # Executor 开始单步
    "step_complete",   # Executor 完成单步
    "replan",          # Replanner 给出新计划
    "report",          # 生成最终报告
    "complete",        # 流程结束
    "error",           # 错误
]


class DiagnosisEvent(BaseModel):
    """诊断 SSE 事件 (示例 schema)."""

    type: EventType = Field(..., description="事件类型")
    stage: str = Field(..., description="阶段标识")
    message: str = Field(default="", description="人类可读的描述")
    data: Dict[str, Any] = Field(default_factory=dict, description="结构化数据载荷")


# ============================================================
# 诊断记录 schema
# ============================================================

class DiagnosisRecordRequest(BaseModel):
    """诊断记录请求."""

    question: str = Field(
        ...,
        description="用户问题或诊断查询",
        min_length=1,
        max_length=2000,
    )
    answer: str = Field(default="", description="诊断结果或回答")
    source: str = Field(
        default="aiops",
        description="来源 (aiops/chat/monitoring)",
    )
    session_id: str = Field(default="", description="会话 ID")
    skill: str = Field(default="", description="使用的技能名称")
    sources: list[str] = Field(default_factory=list, description="参考来源列表")

    model_config = {
        "json_schema_extra": {
            "example": {
                "question": "数据库 CPU 使用率过高",
                "answer": "诊断报告...",
                "source": "aiops",
                "session_id": "diag-001",
                "skill": "database_diagnosis",
                "sources": ["postgresql", "redis"],
            }
        }
    }


class ConversationRecordRequest(BaseModel):
    """对话记录请求."""

    session_id: str = Field(..., description="会话 ID")
    user_message: str = Field(
        ...,
        description="用户消息",
        min_length=1,
        max_length=2000,
    )
    assistant_response: str = Field(default="", description="助手回复")
    source: str = Field(default="chat", description="来源")
    skill: str = Field(default="", description="技能名称")

    model_config = {
        "json_schema_extra": {
            "example": {
                "session_id": "chat-001",
                "user_message": "Redis 内存使用率过高怎么处理?",
                "assistant_response": "建议...",
                "source": "chat",
                "skill": "rag_chat",
            }
        }
    }


class RecordResponse(BaseModel):
    """记录响应."""

    id: str = Field(..., description="记录 ID")
    question: str = Field(..., description="问题")
    answer: str = Field(default="", description="回答")
    source: str = Field(..., description="来源")
    session_id: str = Field(default="", description="会话 ID")
    skill: str = Field(default="", description="技能名称")
    sources: list[str] = Field(default_factory=list, description="参考来源")
    knowledge_base_uploaded: bool = Field(
        default=False, description="是否已上传到知识库"
    )
    ts: float = Field(default=0, description="时间戳")
    ts_iso: str = Field(default="", description="ISO 时间戳")


class RecordListResponse(BaseModel):
    """记录列表响应."""

    total: int = Field(..., description="总记录数")
    page: int = Field(..., description="当前页码")
    page_size: int = Field(..., description="每页数量")
    records: list[RecordResponse] = Field(..., description="记录列表")
