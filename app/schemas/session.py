"""对话会话 Pydantic 模型."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class SessionCreate(BaseModel):
    """创建会话请求."""

    title: str = Field(default="新对话", max_length=200)


class SessionUpdate(BaseModel):
    """更新会话请求."""

    title: str = Field(..., min_length=1, max_length=200)


class MessageOut(BaseModel):
    """消息输出.

    status 字段:
      - success: 正常消息
      - error:   AI 回复失败, error_message 含具体异常信息
      - partial: 流式中断 (兜底场景, 当前未启用)
    """

    id: int
    role: str
    content: str
    image_url: Optional[str] = None
    status: str = "success"
    error_message: Optional[str] = None
    extra: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    model_config = {"from_attributes": True}


class SessionOut(BaseModel):
    """会话输出 (不含消息)."""

    id: str
    title: str
    created_at: datetime
    updated_at: datetime
    message_count: int = 0

    model_config = {"from_attributes": True}


class SessionDetailOut(BaseModel):
    """会话详情 (含消息)."""

    id: str
    title: str
    created_at: datetime
    updated_at: datetime
    messages: list[MessageOut] = []

    model_config = {"from_attributes": True}


class SessionListOut(BaseModel):
    """会话列表输出."""

    sessions: list[SessionOut]
    total: int


class PaginatedMessagesOut(BaseModel):
    """分页消息查询输出.

    用于"进入应用页面加载最新 10 条 + 向前加载更多历史"的场景.

    字段说明:
      - messages: 当前页消息列表, 按时间正序排列 ( oldest -> newest )
      - has_more: 是否还有更早的历史消息可加载
      - oldest_id: 当前返回的最旧消息 id, 作为下次向前加载的 before_id 游标;
                   为 None 表示无消息或已到最早.
    """

    messages: list[MessageOut]
    has_more: bool = False
    oldest_id: Optional[int] = None
