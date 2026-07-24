"""RAG 聊天接口 (流式 SSE).

POST /api/v1/chat/stream
  -> 接收 ChatRequest (session_id, question, top_k)
  -> 返回 SSE 事件流, 每个事件是 {"type": "token"|"end"|"error", "content": "..."}
  -> 前端用 EventSource 接收, 拼接 token 渲染
"""

import json
from typing import AsyncIterator, Optional

from fastapi import APIRouter, Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from loguru import logger
from sse_starlette.sse import EventSourceResponse

from app.core.security import decode_access_token
from app.schemas.chat import ChatRequest
import app.services.chat_memory as chat_memory
import app.services.rag_service as rag_service
from app.services.session_service import session_service

router = APIRouter(prefix="/chat", tags=["chat"])

_optional_bearer = HTTPBearer(auto_error=False)


async def _get_optional_user_id(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_optional_bearer),
) -> Optional[int]:
    """从 JWT token 中提取 user_id, 无 token 时返回 None."""
    if not credentials:
        logger.warning("[chat] 无 Bearer token, user_id=None (请检查前端是否登录)")
        return None
    token_preview = credentials.credentials[:20] + "..." if len(credentials.credentials) > 20 else credentials.credentials
    logger.info(f"[chat] 收到 Bearer token: {token_preview}")
    try:
        payload = decode_access_token(credentials.credentials)
        sub = payload.get("sub")
        user_id = int(sub) if sub else None
        logger.info(f"[chat] JWT 解析成功: payload={payload} -> user_id={user_id}")
        return user_id
    except Exception as e:
        logger.warning(f"[chat] JWT 解析失败: {type(e).__name__}: {e}")
        return None


@router.post(
    "/stream",
    summary="RAG 流式聊天",
    description=(
        "基于知识库的 RAG 单智能体聊天, SSE 流式输出.\n\n"
        "**事件格式** (event=message):\n"
        "```json\n"
        '{"type": "token", "content": "回答的某一段文本"}\n'
        '{"type": "end"}                    // 流结束\n'
        '{"type": "error", "message": "..."}\n'
        "```\n\n"
        "**前端示例**:\n"
        "```javascript\n"
        "const resp = await fetch('/api/v1/chat/stream', {method: 'POST', body: ...});\n"
        "const reader = resp.body.getReader();\n"
        "// ... 读取并拼接 token\n"
        "```"
    ),
)
async def chat_stream(
    req: ChatRequest,
    user_id: Optional[int] = Depends(_get_optional_user_id),
) -> EventSourceResponse:
    logger.info(f"[chat] session={req.session_id}, user={user_id}, q={req.question[:60]}...")

    # 兜底持久化 user 消息：避免前端 fire-and-forget POST 在 SSE 长连接占用
    # 连接池时偶发丢失，导致 DB 里只有 assistant 消息没有对应的 user 消息。
    # 只在该 session 还没有该条 user 消息时写（按内容去重，幂等）。
    if user_id is not None and req.session_id and req.question:
        try:
            detail = session_service.get_session(req.session_id, user_id)
            if detail is not None:
                already_persisted = any(
                    m.role == "user" and m.content == req.question
                    for m in detail.messages
                )
                if not already_persisted:
                    session_service.add_message(
                        req.session_id, "user", req.question, image_url=None
                    )
                    logger.info(
                        f"[chat] 兜底持久化 user 消息 session={req.session_id} len={len(req.question)}"
                    )
        except Exception as e:
            # 持久化失败不阻塞 SSE 流（消息历史的 fallback 是前端自己 POST）
            logger.warning(f"[chat] 兜底持久化 user 消息失败: {type(e).__name__}: {e}")

    async def event_generator() -> AsyncIterator[dict]:
        try:
            async for event in rag_service.stream_chat(
                req.question,
                session_id=req.session_id,
                user_id=user_id,
                top_k=req.top_k,
                web_search=req.web_search,
                mcp_tools=req.mcp_tools,
            ):
                # 向后兼容: 若底层 yield 的是字符串, 默认当 token 包装
                if isinstance(event, str):
                    event = {"type": "token", "content": event}
                yield {
                    "event": "message",
                    "data": json.dumps(event, ensure_ascii=False),
                }
            yield {"event": "message", "data": json.dumps({"type": "end"})}

        except Exception as e:
            logger.exception(f"[chat] stream 异常: {e}")
            yield {
                "event": "message",
                "data": json.dumps(
                    {"type": "error", "message": str(e)}, ensure_ascii=False
                ),
            }

    return EventSourceResponse(event_generator())


@router.get(
    "/sessions/{session_id}/history",
    summary="查看 RAG Chat 会话历史",
    description="返回 Redis 中保存的会话摘要与最近消息。Redis 未启用或不可用时返回空历史。",
)
async def get_chat_history(session_id: str) -> dict:
    session = await chat_memory.load_session(session_id)
    return {
        "session_id": session_id,
        "memory_enabled": await chat_memory.is_available(),
        "summary": session.get("summary") or "",
        "messages": session.get("messages") or [],
    }


@router.delete(
    "/sessions/{session_id}",
    summary="清空 RAG Chat 会话记忆",
    description="删除指定 session_id 的 Redis 会话摘要与消息历史。",
)
async def clear_chat_session(session_id: str) -> dict:
    cleared = await chat_memory.clear_session(session_id)
    return {"session_id": session_id, "cleared": cleared}
