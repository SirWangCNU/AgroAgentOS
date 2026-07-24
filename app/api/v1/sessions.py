"""对话会话 API.

POST   /sessions          创建会话
GET    /sessions           获取会话列表
GET    /sessions/{id}      获取会话详情(含消息)
PUT    /sessions/{id}      更新会话(标题)
DELETE /sessions/{id}      删除会话
POST   /sessions/{id}/messages  添加消息
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger

from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.session import (
    MessageOut,
    SessionCreate,
    SessionDetailOut,
    SessionListOut,
    SessionOut,
    SessionUpdate,
)
from app.services.session_service import session_service

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post("", response_model=ApiResponse[SessionOut], summary="创建会话")
async def create_session(
    data: SessionCreate,
    current_user: User = Depends(get_current_user),
):
    result = session_service.create_session(current_user.id, data)
    logger.info(f"[sessions] 用户 {current_user.username} 创建会话: {result.id}")
    return ApiResponse(code="SUCCESS", data=result)


@router.get("", response_model=ApiResponse[SessionListOut], summary="获取会话列表")
async def list_sessions(
    page: int = 1,
    page_size: int = 50,
    current_user: User = Depends(get_current_user),
):
    result = session_service.list_sessions(current_user.id, page, page_size)
    return ApiResponse(code="SUCCESS", data=result)


@router.get(
    "/{session_id}",
    response_model=ApiResponse[SessionDetailOut],
    summary="获取会话详情",
)
async def get_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
):
    result = session_service.get_session(session_id, current_user.id)
    if not result:
        raise HTTPException(status_code=404, detail="会话不存在")
    return ApiResponse(code="SUCCESS", data=result)


@router.put("/{session_id}", response_model=ApiResponse, summary="更新会话标题")
async def update_session(
    session_id: str,
    data: SessionUpdate,
    current_user: User = Depends(get_current_user),
):
    ok = session_service.update_session(session_id, current_user.id, data)
    if not ok:
        raise HTTPException(status_code=404, detail="会话不存在")
    return ApiResponse(code="SUCCESS", data=None)


@router.delete("/{session_id}", response_model=ApiResponse, summary="删除会话")
async def delete_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
):
    ok = session_service.delete_session(session_id, current_user.id)
    if not ok:
        raise HTTPException(status_code=404, detail="会话不存在")
    logger.info(f"[sessions] 用户 {current_user.username} 删除会话: {session_id}")
    return ApiResponse(code="SUCCESS", data=None)


@router.post(
    "/{session_id}/messages",
    response_model=ApiResponse[MessageOut],
    summary="添加消息",
)
async def add_message(
    session_id: str,
    role: str = "user",
    content: str = "",
    image_url: Optional[str] = None,
    current_user: User = Depends(get_current_user),
):
    # 验证会话属于当前用户
    session = session_service.get_session(session_id, current_user.id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    result = session_service.add_message(session_id, role, content, image_url)
    return ApiResponse(code="SUCCESS", data=result)
