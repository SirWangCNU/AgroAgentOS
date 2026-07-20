"""对话会话 API.

POST   /sessions                       创建会话
GET    /sessions                       获取会话列表
GET    /sessions/{id}                  获取会话详情 (含全量消息)
GET    /sessions/{id}/messages         分页查询消息 (游标分页, 默认最新 10 条)
PUT    /sessions/{id}                  更新会话 (标题)
DELETE /sessions/{id}                  删除会话 (级联删除消息)
POST   /sessions/{id}/messages         添加消息 (强制归属校验)
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from loguru import logger

from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.session import (
    MessageOut,
    PaginatedMessagesOut,
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


# ✅ 路由优先级：具体路径放前面，避免参数路由/{session_id}拦截了/messages请求
@router.get(
    "/{session_id}/messages",
    response_model=ApiResponse[PaginatedMessagesOut],
    summary="分页查询会话消息",
)
async def list_messages(
    session_id: str,
    limit: int = Query(default=10, ge=1, le=50, description="每页条数 (1-50)"),
    before_id: Optional[int] = Query(
        default=None,
        description="游标: 返回 id < before_id 的消息. 首次加载留空, 向前加载用上次返回的 oldest_id",
    ),
    current_user: User = Depends(get_current_user),
):
    """分页查询会话消息 (游标分页).

    用法:
      - 进入应用页面首次加载: limit=10, before_id=None → 返回最新 10 条
      - 向前加载更多: limit=10, before_id=<上次返回的 oldest_id>

    返回的 messages 按时间正序排列 (oldest -> newest), 前端可直接 append 显示.
    has_more 为 True 表示还有更早的消息可加载.
    """
    try:
        result = session_service.get_messages_paginated(
            session_id, current_user.id, limit=limit, before_id=before_id
        )
    except ValueError as exc:
        # 会话不存在或不属于该用户
        raise HTTPException(status_code=404, detail=str(exc))
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
    """添加消息.

    安全: session_service.add_message 内部强制校验 (session_id, user_id) 归属,
    非会话所有者调用会抛 ValueError → 404.
    """
    try:
        result = session_service.add_message(
            session_id, current_user.id, role, content, image_url
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return ApiResponse(code="SUCCESS", data=result)
