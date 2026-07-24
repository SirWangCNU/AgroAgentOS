"""对话会话 Pydantic 模型."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class SessionCreate(BaseModel):
    """创建会话请求."""

    title: str = Field(default="新对话", max_length=200)


class SessionUpdate(BaseModel):
    """更新会话请求."""

    title: str = Field(..., min_length=1, max_length=200)


class MessageOut(BaseModel):
    """消息输出."""

    id: int
    role: str
    content: str
    image_url: Optional[str] = None
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
