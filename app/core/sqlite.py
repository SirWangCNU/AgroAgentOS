"""SQLite 轻量级数据库管理.

职责:
  - 持久化存储会话记录、Agent执行日志等结构化数据
  - 为未来业务扩展预留表结构
  - 使用 SQLAlchemy ORM 管理表结构
"""

from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Generator

from loguru import logger
from sqlalchemy import Column, DateTime, Integer, String, Text, create_engine, event, func
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings

Base = declarative_base()


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(128), unique=True, nullable=False, index=True)
    user_id = Column(String(128), nullable=True, index=True)
    title = Column(String(256), nullable=True)
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())
    extra_json = Column(Text, nullable=True)

    @property
    def extra(self) -> dict[str, Any]:
        if not self.extra_json:
            return {}
        try:
            return json.loads(self.extra_json)
        except Exception:
            return {}

    def set_extra(self, data: dict[str, Any]) -> None:
        self.extra_json = json.dumps(data, ensure_ascii=False, default=str)


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(128), nullable=False, index=True)
    role = Column(String(32), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, default=func.now())
    extra_json = Column(Text, nullable=True)

    @property
    def extra(self) -> dict[str, Any]:
        if not self.extra_json:
            return {}
        try:
            return json.loads(self.extra_json)
        except Exception:
            return {}

    def set_extra(self, data: dict[str, Any]) -> None:
        self.extra_json = json.dumps(data, ensure_ascii=False, default=str)


class AgentExecutionLog(Base):
    __tablename__ = "agent_execution_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(128), nullable=True, index=True)
    skill_name = Column(String(128), nullable=True, index=True)
    step_index = Column(Integer, nullable=False)
    action = Column(String(64), nullable=False)
    tool_name = Column(String(128), nullable=True)
    result = Column(Text, nullable=True)
    error = Column(Text, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    created_at = Column(DateTime, nullable=False, default=func.now())


class HistoryRecord(Base):
    __tablename__ = "history_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    record_id = Column(String(32), unique=True, nullable=False, index=True)
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=True)
    source = Column(String(32), nullable=False, index=True)
    session_id = Column(String(128), nullable=True, index=True)
    skill = Column(String(128), nullable=True)
    sources_json = Column(Text, nullable=True)
    extra_json = Column(Text, nullable=True)
    knowledge_base_uploaded = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=func.now())

    @property
    def sources(self) -> list[str]:
        if not self.sources_json:
            return []
        try:
            return json.loads(self.sources_json)
        except Exception:
            return []

    def set_sources(self, data: list[str]) -> None:
        self.sources_json = json.dumps(data, ensure_ascii=False, default=str)

    @property
    def extra(self) -> dict[str, Any]:
        if not self.extra_json:
            return {}
        try:
            return json.loads(self.extra_json)
        except Exception:
            return {}

    def set_extra(self, data: dict[str, Any]) -> None:
        self.extra_json = json.dumps(data, ensure_ascii=False, default=str)


class BusinessRecord(Base):
    __tablename__ = "business_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    record_type = Column(String(64), nullable=False, index=True)
    record_key = Column(String(256), nullable=True, index=True)
    title = Column(String(256), nullable=True)
    content_json = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())

    @property
    def content(self) -> dict[str, Any]:
        if not self.content_json:
            return {}
        try:
            return json.loads(self.content_json)
        except Exception:
            return {}

    def set_content(self, data: dict[str, Any]) -> None:
        self.content_json = json.dumps(data, ensure_ascii=False, default=str)


class Alert(Base):
    """告警记录表 - 结构化存储 Alertmanager 推送的告警."""

    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    alert_id = Column(String(64), unique=True, nullable=False, index=True)
    alertname = Column(String(256), nullable=False, index=True)
    severity = Column(String(32), nullable=False, index=True)  # critical/warning/info
    status = Column(String(32), nullable=False, default="firing", index=True)  # firing/resolved/acknowledged
    instance = Column(String(256), nullable=True)
    service = Column(String(128), nullable=True, index=True)
    summary = Column(Text, nullable=True)
    description = Column(Text, nullable=True)
    raw_labels = Column(Text, nullable=True)  # JSON
    raw_annotations = Column(Text, nullable=True)  # JSON
    fingerprint = Column(String(64), nullable=True, index=True)
    source = Column(String(64), nullable=False, default="alertmanager")
    diagnosis_session_id = Column(String(128), nullable=True)
    diagnosis_status = Column(String(32), nullable=True, default="pending")  # pending/running/completed/failed
    diagnosis_report = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=func.now())
    resolved_at = Column(DateTime, nullable=True)
    acknowledged_at = Column(DateTime, nullable=True)
    acknowledged_by = Column(String(128), nullable=True)

    @property
    def labels(self) -> dict[str, Any]:
        if not self.raw_labels:
            return {}
        try:
            return json.loads(self.raw_labels)
        except Exception:
            return {}

    def set_labels(self, data: dict[str, Any]) -> None:
        self.raw_labels = json.dumps(data, ensure_ascii=False, default=str)

    @property
    def annotations(self) -> dict[str, Any]:
        if not self.raw_annotations:
            return {}
        try:
            return json.loads(self.raw_annotations)
        except Exception:
            return {}

    def set_annotations(self, data: dict[str, Any]) -> None:
        self.raw_annotations = json.dumps(data, ensure_ascii=False, default=str)


class AgentRun(Base):
    """Agent 运行记录表 - 记录每次诊断的详细信息."""

    __tablename__ = "agent_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(64), unique=True, nullable=False, index=True)
    session_id = Column(String(128), nullable=True, index=True)
    query = Column(Text, nullable=True)
    selected_skill = Column(String(128), nullable=True, index=True)
    status = Column(String(32), nullable=True, default="running")  # running/completed/failed
    total_steps = Column(Integer, nullable=True, default=0)
    total_tool_calls = Column(Integer, nullable=True, default=0)
    total_tokens = Column(Integer, nullable=True, default=0)
    input_tokens = Column(Integer, nullable=True, default=0)
    output_tokens = Column(Integer, nullable=True, default=0)
    total_ms = Column(Integer, nullable=True, default=0)
    model_used = Column(String(128), nullable=True)
    reroute_count = Column(Integer, nullable=True, default=0)
    transitions_json = Column(Text, nullable=True)  # Full transition_history as JSON
    report_preview = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=func.now())

    @property
    def transitions(self) -> list[dict[str, Any]]:
        if not self.transitions_json:
            return []
        try:
            return json.loads(self.transitions_json)
        except Exception:
            return []

    def set_transitions(self, data: list[dict[str, Any]]) -> None:
        self.transitions_json = json.dumps(data, ensure_ascii=False, default=str)


class SQLiteManager:
    def __init__(self) -> None:
        self._engine: Engine | None = None
        self._session_factory: sessionmaker[Session] | None = None

    def connect(self) -> None:
        db_path = settings.sqlite_db_path
        db_dir = Path(db_path).parent
        if db_dir.name:
            db_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"连接 SQLite 数据库: {db_path}")
        self._engine = create_engine(
            f"sqlite:///{db_path}",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            echo=settings.debug,
        )

        @event.listens_for(Engine, "connect")
        def _set_sqlite_pragma(dbapi_conn: Any, connection_record: Any) -> None:
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        Base.metadata.create_all(self._engine)
        self._session_factory = sessionmaker(bind=self._engine, expire_on_commit=False)
        logger.info("SQLite 数据库初始化完成")

    def disconnect(self) -> None:
        if self._engine:
            self._engine.dispose()
            self._engine = None
            self._session_factory = None
            logger.info("SQLite 数据库连接已断开")

    def is_alive(self) -> bool:
        if not self._engine:
            return False
        try:
            with self._engine.connect() as conn:
                conn.execute(func.random())
            return True
        except Exception:
            return False

    @contextmanager
    def session(self) -> Generator[Session, None, None]:
        if not self._session_factory:
            self.connect()
        session = self._session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def save_message(
        self,
        session_id: str,
        role: str,
        content: str,
        extra: dict[str, Any] | None = None,
    ) -> ChatMessage:
        with self.session() as sess:
            msg = ChatMessage(session_id=session_id, role=role, content=content)
            if extra:
                msg.set_extra(extra)
            sess.add(msg)
            sess.flush()
            sess.expunge(msg)
            return msg

    def get_messages(
        self, session_id: str, limit: int = 100, offset: int = 0
    ) -> list[ChatMessage]:
        with self.session() as sess:
            return (
                sess.query(ChatMessage)
                .filter(ChatMessage.session_id == session_id)
                .order_by(ChatMessage.created_at.desc())
                .offset(offset)
                .limit(limit)
                .all()
            )

    def get_or_create_session(self, session_id: str, user_id: str | None = None) -> ChatSession:
        with self.session() as sess:
            session = sess.query(ChatSession).filter(ChatSession.session_id == session_id).first()
            if not session:
                session = ChatSession(session_id=session_id, user_id=user_id)
                sess.add(session)
                sess.flush()
            sess.expunge(session)
            return session

    def update_session_title(self, session_id: str, title: str) -> None:
        with self.session() as sess:
            session = sess.query(ChatSession).filter(ChatSession.session_id == session_id).first()
            if session:
                session.title = title
                sess.flush()

    def save_execution_log(
        self,
        session_id: str | None,
        skill_name: str | None,
        step_index: int,
        action: str,
        tool_name: str | None = None,
        result: str | None = None,
        error: str | None = None,
        duration_ms: int | None = None,
    ) -> AgentExecutionLog:
        with self.session() as sess:
            log = AgentExecutionLog(
                session_id=session_id,
                skill_name=skill_name,
                step_index=step_index,
                action=action,
                tool_name=tool_name,
                result=result,
                error=error,
                duration_ms=duration_ms,
            )
            sess.add(log)
            sess.flush()
            sess.expunge(log)
            return log

    def save_history_record(
        self,
        record_id: str,
        question: str,
        answer: str = "",
        source: str = "chat",
        session_id: str = "",
        skill: str = "",
        sources: list[str] | None = None,
        extra: dict[str, Any] | None = None,
    ) -> HistoryRecord:
        with self.session() as sess:
            record = HistoryRecord(
                record_id=record_id,
                question=question,
                answer=answer,
                source=source,
                session_id=session_id,
                skill=skill,
            )
            if sources:
                record.set_sources(sources)
            if extra:
                record.set_extra(extra)
            sess.add(record)
            sess.flush()
            sess.expunge(record)
            return record

    def get_history_records(
        self,
        page: int = 1,
        page_size: int = 20,
        source: str | None = None,
    ) -> tuple[list[HistoryRecord], int]:
        with self.session() as sess:
            query = sess.query(HistoryRecord)
            if source:
                query = query.filter(HistoryRecord.source == source)
            total = query.count()
            offset = (page - 1) * page_size
            records = (
                query.order_by(HistoryRecord.created_at.desc())
                .offset(offset)
                .limit(page_size)
                .all()
            )
            return records, total

    def get_history_record(self, record_id: str) -> HistoryRecord | None:
        with self.session() as sess:
            return sess.query(HistoryRecord).filter(HistoryRecord.record_id == record_id).first()

    def update_history_kb_uploaded(self, record_id: str, uploaded: bool) -> None:
        with self.session() as sess:
            record = sess.query(HistoryRecord).filter(HistoryRecord.record_id == record_id).first()
            if record:
                record.knowledge_base_uploaded = 1 if uploaded else 0
                sess.flush()

    def delete_history_record(self, record_id: str) -> bool:
        with self.session() as sess:
            record = sess.query(HistoryRecord).filter(HistoryRecord.record_id == record_id).first()
            if record:
                sess.delete(record)
                sess.flush()
                return True
            return False

    def clear_history_records(self, source: str | None = None) -> int:
        with self.session() as sess:
            query = sess.query(HistoryRecord)
            if source:
                query = query.filter(HistoryRecord.source == source)
            count = query.delete()
            sess.flush()
            return count

    def save_business_record(
        self,
        record_type: str,
        record_key: str | None,
        title: str | None,
        content: dict[str, Any],
    ) -> BusinessRecord:
        with self.session() as sess:
            record = BusinessRecord(
                record_type=record_type,
                record_key=record_key,
                title=title,
            )
            record.set_content(content)
            sess.add(record)
            sess.flush()
            sess.expunge(record)
            return record

    def get_business_records(
        self, record_type: str, limit: int = 100, offset: int = 0
    ) -> list[BusinessRecord]:
        with self.session() as sess:
            return (
                sess.query(BusinessRecord)
                .filter(BusinessRecord.record_type == record_type)
                .order_by(BusinessRecord.created_at.desc())
                .offset(offset)
                .limit(limit)
                .all()
            )


sqlite_manager = SQLiteManager()
