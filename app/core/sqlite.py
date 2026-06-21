"""AgroAgentOS 数据库模型定义.

职责:
  - 定义所有 ORM 模型 (ChatSession, ChatMessage, User, Farm 等)
  - 提供 SQLAlchemy Base 声明基类
  - 向后兼容: 导出 sqlite_manager 作为 database_manager 的别名

数据库设计原则:
  - 独立于原 AIOps 项目，全新农业场景
  - 支持农业问答、天气查询、营销生成、病虫害诊断等业务

注意:
  - 实际数据库连接管理已迁移到 database.py (DatabaseManager)
  - 本文件保留 SQLiteManager 类以保持向后兼容
  - 新代码应使用 from app.core.database import database_manager
"""

from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Generator

from loguru import logger
from sqlalchemy import Column, DateTime, Float, Integer, String, Text, create_engine, event, func
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


class WeatherQuery(Base):
    """天气查询记录表 - 记录天气查询历史和农业建议."""

    __tablename__ = "weather_queries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    query_id = Column(String(64), unique=True, nullable=False, index=True)
    location = Column(String(128), nullable=False, index=True)
    temperature = Column(Float, nullable=True)
    humidity = Column(Integer, nullable=True)
    wind_speed = Column(Float, nullable=True)
    wind_level = Column(Integer, nullable=True)
    condition = Column(String(64), nullable=True)
    rain_probability = Column(Integer, nullable=True)
    agriculture_advice = Column(Text, nullable=True)
    session_id = Column(String(128), nullable=True, index=True)
    created_at = Column(DateTime, nullable=False, default=func.now())


class MarketingTask(Base):
    """营销任务表 - 记录农产品营销内容生成任务."""

    __tablename__ = "marketing_tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String(64), unique=True, nullable=False, index=True)
    product_name = Column(String(256), nullable=False)
    product_features = Column(Text, nullable=True)  # JSON array
    target_platform = Column(String(64), nullable=False)  # douyin/xiaohongshu/live_stream/wechat
    content_style = Column(String(64), nullable=True)  # professional/funny/emotional/storytelling
    generated_title = Column(Text, nullable=True)
    generated_content = Column(Text, nullable=True)
    generated_script = Column(Text, nullable=True)
    session_id = Column(String(128), nullable=True, index=True)
    status = Column(String(32), nullable=False, default="pending")  # pending/generating/completed/failed
    created_at = Column(DateTime, nullable=False, default=func.now())
    completed_at = Column(DateTime, nullable=True)


class PestDiagnosis(Base):
    """病虫害诊断记录表 - 记录病虫害诊断历史."""

    __tablename__ = "pest_diagnoses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    diagnosis_id = Column(String(64), unique=True, nullable=False, index=True)
    crop_type = Column(String(128), nullable=False, index=True)
    symptoms = Column(Text, nullable=False)
    affected_part = Column(String(64), nullable=True)  # leaf/stem/root/fruit/flower
    diagnosis_result = Column(Text, nullable=True)  # JSON: possible diseases
    treatment_plan = Column(Text, nullable=True)
    session_id = Column(String(128), nullable=True, index=True)
    status = Column(String(32), nullable=False, default="pending")  # pending/diagnosed/failed
    created_at = Column(DateTime, nullable=False, default=func.now())


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

    # ==================== 农业业务方法 ====================

    def save_weather_query(
        self,
        query_id: str,
        location: str,
        temperature: float | None = None,
        humidity: int | None = None,
        wind_speed: float | None = None,
        wind_level: int | None = None,
        condition: str | None = None,
        rain_probability: int | None = None,
        agriculture_advice: str | None = None,
        session_id: str | None = None,
    ) -> WeatherQuery:
        """保存天气查询记录."""
        with self.session() as sess:
            query = WeatherQuery(
                query_id=query_id,
                location=location,
                temperature=temperature,
                humidity=humidity,
                wind_speed=wind_speed,
                wind_level=wind_level,
                condition=condition,
                rain_probability=rain_probability,
                agriculture_advice=agriculture_advice,
                session_id=session_id,
            )
            sess.add(query)
            sess.flush()
            sess.expunge(query)
            return query

    def save_marketing_task(
        self,
        task_id: str,
        product_name: str,
        product_features: list[str] | None = None,
        target_platform: str = "douyin",
        content_style: str = "professional",
        session_id: str | None = None,
    ) -> MarketingTask:
        """保存营销任务."""
        with self.session() as sess:
            task = MarketingTask(
                task_id=task_id,
                product_name=product_name,
                target_platform=target_platform,
                content_style=content_style,
                session_id=session_id,
            )
            if product_features:
                task.product_features = json.dumps(product_features, ensure_ascii=False)
            sess.add(task)
            sess.flush()
            sess.expunge(task)
            return task

    def update_marketing_result(
        self,
        task_id: str,
        title: str | None = None,
        content: str | None = None,
        script: str | None = None,
        status: str = "completed",
    ) -> None:
        """更新营销任务结果."""
        with self.session() as sess:
            task = sess.query(MarketingTask).filter(MarketingTask.task_id == task_id).first()
            if task:
                if title:
                    task.generated_title = title
                if content:
                    task.generated_content = content
                if script:
                    task.generated_script = script
                task.status = status
                task.completed_at = func.now()
                sess.flush()

    def save_pest_diagnosis(
        self,
        diagnosis_id: str,
        crop_type: str,
        symptoms: str,
        affected_part: str | None = None,
        session_id: str | None = None,
    ) -> PestDiagnosis:
        """保存病虫害诊断记录."""
        with self.session() as sess:
            diagnosis = PestDiagnosis(
                diagnosis_id=diagnosis_id,
                crop_type=crop_type,
                symptoms=symptoms,
                affected_part=affected_part,
                session_id=session_id,
            )
            sess.add(diagnosis)
            sess.flush()
            sess.expunge(diagnosis)
            return diagnosis

    def update_pest_diagnosis_result(
        self,
        diagnosis_id: str,
        result: dict[str, Any] | None = None,
        treatment_plan: str | None = None,
        status: str = "diagnosed",
    ) -> None:
        """更新病虫害诊断结果."""
        with self.session() as sess:
            diagnosis = sess.query(PestDiagnosis).filter(PestDiagnosis.diagnosis_id == diagnosis_id).first()
            if diagnosis:
                if result:
                    diagnosis.diagnosis_result = json.dumps(result, ensure_ascii=False)
                if treatment_plan:
                    diagnosis.treatment_plan = treatment_plan
                diagnosis.status = status
                sess.flush()

    def get_marketing_tasks(
        self,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[MarketingTask], int]:
        """获取营销任务列表."""
        with self.session() as sess:
            query = sess.query(MarketingTask)
            total = query.count()
            offset = (page - 1) * page_size
            tasks = (
                query.order_by(MarketingTask.created_at.desc())
                .offset(offset)
                .limit(page_size)
                .all()
            )
            return tasks, total

    def get_pest_diagnoses(
        self,
        page: int = 1,
        page_size: int = 20,
        crop_type: str | None = None,
    ) -> tuple[list[PestDiagnosis], int]:
        """获取病虫害诊断列表."""
        with self.session() as sess:
            query = sess.query(PestDiagnosis)
            if crop_type:
                query = query.filter(PestDiagnosis.crop_type == crop_type)
            total = query.count()
            offset = (page - 1) * page_size
            diagnoses = (
                query.order_by(PestDiagnosis.created_at.desc())
                .offset(offset)
                .limit(page_size)
                .all()
            )
            return diagnoses, total

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


class VideoTask(Base):
    """视频生成任务表."""

    __tablename__ = "video_tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String(128), unique=True, nullable=False, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    prompt = Column(Text, nullable=False)
    image_url = Column(String(512), nullable=True)
    model = Column(String(128), nullable=True)
    status = Column(String(32), nullable=False, default="pending")
    video_url = Column(String(1024), nullable=True)
    error_message = Column(Text, nullable=True)
    duration = Column(Float, nullable=True)
    extra_json = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())

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


# 向后兼容: 保留 SQLiteManager 类，但 sqlite_manager 单例使用统一的 DatabaseManager
# 新代码建议使用: from app.core.database import database_manager


def __getattr__(name: str):
    """模块级懒加载，避免循环导入."""
    if name == "sqlite_manager":
        from app.core.database import database_manager
        return database_manager
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
