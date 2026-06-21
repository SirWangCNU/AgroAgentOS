"""视频生成接口的数据模型."""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class VideoTaskStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class VideoGenResponse(BaseModel):
    task_id: str = Field(..., description="任务 ID")
    status: VideoTaskStatus = Field(..., description="任务状态")
    message: str = Field(default="任务已提交", description="状态消息")


class VideoTaskDetail(BaseModel):
    task_id: str = Field(..., description="任务 ID")
    prompt: str = Field(..., description="视频描述")
    image_url: Optional[str] = Field(None, description="输入图片 URL")
    status: VideoTaskStatus = Field(..., description="任务状态")
    video_url: Optional[str] = Field(None, description="生成的视频 URL")
    error_message: Optional[str] = Field(None, description="错误信息")
    duration: Optional[float] = Field(None, description="视频时长 (秒)")
    model: Optional[str] = Field(None, description="使用的模型")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")


class VideoTaskListResponse(BaseModel):
    total: int = Field(..., description="总任务数")
    tasks: list[VideoTaskDetail] = Field(default_factory=list, description="任务列表")
