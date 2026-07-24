"""对话会话 ORM 模型."""

from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func

from app.core.sqlite import Base


class ChatSession(Base):
    """对话会话."""

    __tablename__ = "chat_sessions"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(128), nullable=False, unique=True, index=True)
    user_id = Column(String(128), nullable=True)
    title = Column(String(256), default="新对话")
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    extra_json = Column(Text, nullable=True)


class ChatSessionMessage(Base):
    """会话消息."""

    __tablename__ = "chat_session_messages"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(
        String(128), ForeignKey("chat_sessions.session_id", ondelete="CASCADE"), nullable=False, index=True
    )
    role = Column(String(20), nullable=False)  # user / assistant
    content = Column(Text, nullable=False)
    image_url = Column(String(500), nullable=True)  # 图片 URL (可选)
    created_at = Column(DateTime, default=func.now())
