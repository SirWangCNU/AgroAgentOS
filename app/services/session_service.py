"""对话会话业务逻辑."""

from __future__ import annotations

import uuid
from typing import Optional

from loguru import logger
from sqlalchemy import func

from app.core.sqlite import sqlite_manager
from app.models.session import ChatSession, ChatSessionMessage
from app.schemas.session import (
    MessageOut,
    SessionCreate,
    SessionDetailOut,
    SessionListOut,
    SessionOut,
)


class SessionService:
    """对话会话管理服务."""

    def create_session(self, user_id: int, data: SessionCreate) -> SessionOut:
        """创建新会话."""
        session_uuid = str(uuid.uuid4())
        with sqlite_manager.session() as sess:
            session = ChatSession(
                session_id=session_uuid,
                user_id=str(user_id),
                title=data.title,
            )
            sess.add(session)
            sess.flush()
            return SessionOut(
                id=session.session_id,
                title=session.title,
                created_at=session.created_at,
                updated_at=session.updated_at,
                message_count=0,
            )

    def list_sessions(
        self, user_id: int, page: int = 1, page_size: int = 50
    ) -> SessionListOut:
        """获取用户会话列表."""
        with sqlite_manager.session() as sess:
            query = (
                sess.query(ChatSession)
                .filter(ChatSession.user_id == str(user_id))
                .order_by(ChatSession.updated_at.desc())
            )
            total = query.count()
            sessions = query.offset((page - 1) * page_size).limit(page_size).all()

            result = []
            for s in sessions:
                msg_count = (
                    sess.query(func.count(ChatSessionMessage.id))
                    .filter(ChatSessionMessage.session_id == s.session_id)
                    .scalar()
                    or 0
                )
                result.append(
                    SessionOut(
                        id=s.session_id,
                        title=s.title,
                        created_at=s.created_at,
                        updated_at=s.updated_at,
                        message_count=msg_count,
                    )
                )
            return SessionListOut(sessions=result, total=total)

    def get_session(self, session_uuid: str, user_id: int) -> Optional[SessionDetailOut]:
        """获取会话详情 (含消息)."""
        with sqlite_manager.session() as sess:
            session = (
                sess.query(ChatSession)
                .filter(
                    ChatSession.session_id == session_uuid,
                    ChatSession.user_id == str(user_id),
                )
                .first()
            )
            if not session:
                return None

            messages = (
                sess.query(ChatSessionMessage)
                .filter(ChatSessionMessage.session_id == session.session_id)
                .order_by(ChatSessionMessage.created_at.asc())
                .all()
            )

            return SessionDetailOut(
                id=session.session_id,
                title=session.title,
                created_at=session.created_at,
                updated_at=session.updated_at,
                messages=[
                    MessageOut(
                        id=m.id,
                        role=m.role,
                        content=m.content,
                        image_url=m.image_url,
                        created_at=m.created_at,
                    )
                    for m in messages
                ],
            )

    def update_session(
        self, session_uuid: str, user_id: int, data
    ) -> bool:
        """更新会话标题."""
        with sqlite_manager.session() as sess:
            session = (
                sess.query(ChatSession)
                .filter(
                    ChatSession.session_id == session_uuid,
                    ChatSession.user_id == str(user_id),
                )
                .first()
            )
            if not session:
                return False
            session.title = data.title
            return True

    def delete_session(self, session_uuid: str, user_id: int) -> bool:
        """删除会话."""
        with sqlite_manager.session() as sess:
            session = (
                sess.query(ChatSession)
                .filter(
                    ChatSession.session_id == session_uuid,
                    ChatSession.user_id == str(user_id),
                )
                .first()
            )
            if not session:
                return False
            # 先删消息
            sess.query(ChatSessionMessage).filter(
                ChatSessionMessage.session_id == session.session_id
            ).delete()
            sess.delete(session)
            return True

    def add_message(
        self,
        session_uuid: str,
        role: str,
        content: str,
        image_url: Optional[str] = None,
    ) -> MessageOut:
        """向会话添加消息."""
        with sqlite_manager.session() as sess:
            # 找到 session 的 integer id
            session = sess.query(ChatSession).filter(
                ChatSession.session_id == session_uuid
            ).first()
            if not session:
                raise ValueError(f"会话不存在: {session_uuid}")

            msg = ChatSessionMessage(
                session_id=session.session_id,
                role=role,
                content=content,
                image_url=image_url,
            )
            sess.add(msg)
            sess.flush()

            return MessageOut(
                id=msg.id,
                role=msg.role,
                content=msg.content,
                image_url=msg.image_url,
                created_at=msg.created_at,
            )

    def auto_title_from_message(self, session_uuid: str, content: str) -> None:
        """用第一条用户消息自动设置会话标题."""
        title = content[:30].strip()
        if len(content) > 30:
            title += "..."
        with sqlite_manager.session() as sess:
            session = sess.query(ChatSession).filter(
                ChatSession.session_id == session_uuid
            ).first()
            if session and session.title == "新对话":
                session.title = title


session_service = SessionService()
