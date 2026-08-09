"""AgroAgentOS 统一数据库管理器.

职责:
  - 根据配置自动切换 SQLite / MySQL
  - 提供统一的会话管理和业务方法
  - 保持与原有 SQLiteManager 接口兼容

使用方式:
  from app.core.database import database_manager
  with database_manager.session() as sess:
      sess.query(User).all()
"""

from __future__ import annotations

import json
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator

from loguru import logger
from sqlalchemy import create_engine, event, func
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool, QueuePool

from app.config import settings

# 复用 sqlite.py 中定义的 ORM 模型和 Base
from app.core.sqlite import (
    Base,
    BusinessRecord,
    ChatMessage,
    ChatSession,
    HistoryRecord,
    PestDiagnosis,
    WeatherQuery,
)


class DatabaseManager:
    """统一数据库管理器，支持 SQLite / MySQL 切换."""

    def __init__(self) -> None:
        self._engine: Engine | None = None
        self._session_factory: sessionmaker[Session] | None = None
        self._db_type: str = "unknown"

    @property
    def db_type(self) -> str:
        """当前数据库类型: sqlite / mysql."""
        return self._db_type

    def connect(self) -> None:
        """根据配置连接数据库."""
        if settings.use_sqlite:
            self._connect_sqlite()
        else:
            self._connect_mysql()

    def _connect_sqlite(self) -> None:
        """连接 SQLite 数据库."""
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
        self._db_type = "sqlite"
        logger.info("SQLite 数据库初始化完成")

    def _connect_mysql(self) -> None:
        """连接 MySQL 数据库."""
        url = settings.database_url
        logger.info(f"连接 MySQL 数据库: {settings.mysql_host}:{settings.mysql_port}/{settings.mysql_database}")

        self._engine = create_engine(
            url,
            poolclass=QueuePool,
            pool_size=5,
            max_overflow=10,
            pool_recycle=3600,
            pool_pre_ping=True,
            echo=settings.debug,
        )

        # 确保数据库存在（自动创建）
        self._ensure_database()

        Base.metadata.create_all(self._engine)
        self._session_factory = sessionmaker(bind=self._engine, expire_on_commit=False)
        self._db_type = "mysql"
        logger.info("MySQL 数据库初始化完成")

    def _ensure_database(self) -> None:
        """确保 MySQL 数据库存在，不存在则自动创建."""
        from sqlalchemy import text

        # 用无数据库的 URL 连接，创建数据库
        base_url = (
            f"mysql+pymysql://{settings.mysql_user}:{settings.mysql_password}"
            f"@{settings.mysql_host}:{settings.mysql_port}/?charset={settings.mysql_charset}"
        )
        temp_engine = create_engine(base_url)
        try:
            with temp_engine.connect() as conn:
                conn.execute(text(
                    f"CREATE DATABASE IF NOT EXISTS `{settings.mysql_database}` "
                    f"CHARACTER SET {settings.mysql_charset} COLLATE {settings.mysql_charset}_general_ci"
                ))
                conn.commit()
            logger.info(f"MySQL 数据库 '{settings.mysql_database}' 已就绪")
        finally:
            temp_engine.dispose()

    def disconnect(self) -> None:
        """断开数据库连接."""
        if self._engine:
            self._engine.dispose()
            self._engine = None
            self._session_factory = None
            logger.info(f"{self._db_type.upper()} 数据库连接已断开")

    def is_alive(self) -> bool:
        """检查数据库连接是否存活."""
        if not self._engine:
            return False
        try:
            with self._engine.connect() as conn:
                conn.execute(func.now())
            return True
        except Exception:
            return False

    @contextmanager
    def session(self) -> Generator[Session, None, None]:
        """获取数据库会话（上下文管理器）."""
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

    # ==================== 会话管理方法 ====================

    def save_message(
        self,
        session_id: str,
        role: str,
        content: str,
        extra: dict[str, Any] | None = None,
    ) -> ChatMessage:
        """保存聊天消息."""
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
        """获取聊天消息列表."""
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
        """获取或创建会话."""
        with self.session() as sess:
            session = sess.query(ChatSession).filter(ChatSession.session_id == session_id).first()
            if not session:
                session = ChatSession(session_id=session_id, user_id=user_id)
                sess.add(session)
                sess.flush()
            sess.expunge(session)
            return session

    def update_session_title(self, session_id: str, title: str) -> None:
        """更新会话标题."""
        with self.session() as sess:
            session = sess.query(ChatSession).filter(ChatSession.session_id == session_id).first()
            if session:
                session.title = title
                sess.flush()

    # ==================== 历史记录方法 ====================

    def save_history_record(
        self,
        record_id: str,
        user_id: int,
        question: str,
        answer: str = "",
        source: str = "chat",
        session_id: str = "",
        skill: str = "",
        sources: list[str] | None = None,
        extra: dict[str, Any] | None = None,
    ) -> HistoryRecord:
        """保存历史记录."""
        with self.session() as sess:
            record = HistoryRecord(
                record_id=record_id,
                user_id=user_id,
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
        user_id: int,
        page: int = 1,
        page_size: int = 20,
        source: str | None = None,
    ) -> tuple[list[HistoryRecord], int]:
        """获取历史记录列表（分页）."""
        with self.session() as sess:
            query = sess.query(HistoryRecord).filter(HistoryRecord.user_id == user_id)
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

    def get_history_record(self, record_id: str, user_id: int) -> HistoryRecord | None:
        """获取单条历史记录."""
        with self.session() as sess:
            return (
                sess.query(HistoryRecord)
                .filter(HistoryRecord.record_id == record_id, HistoryRecord.user_id == user_id)
                .first()
            )

    def get_history_record_for_admin(self, record_id: str) -> HistoryRecord | None:
        """供受信任管理员审核时读取历史记录。"""
        with self.session() as sess:
            return sess.query(HistoryRecord).filter(HistoryRecord.record_id == record_id).first()

    def update_history_kb_uploaded(self, record_id: str, uploaded: bool) -> None:
        """更新历史记录的知识库上传状态."""
        with self.session() as sess:
            record = sess.query(HistoryRecord).filter(HistoryRecord.record_id == record_id).first()
            if record:
                record.knowledge_base_uploaded = 1 if uploaded else 0
                sess.flush()

    def delete_history_record(self, record_id: str, user_id: int) -> bool:
        """删除历史记录."""
        with self.session() as sess:
            record = (
                sess.query(HistoryRecord)
                .filter(HistoryRecord.record_id == record_id, HistoryRecord.user_id == user_id)
                .first()
            )
            if record:
                sess.delete(record)
                sess.flush()
                return True
            return False

    def clear_history_records(self, user_id: int, source: str | None = None) -> int:
        """清空历史记录."""
        with self.session() as sess:
            query = sess.query(HistoryRecord).filter(HistoryRecord.user_id == user_id)
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
        """保存业务记录."""
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
        """获取业务记录列表."""
        with self.session() as sess:
            return (
                sess.query(BusinessRecord)
                .filter(BusinessRecord.record_type == record_type)
                .order_by(BusinessRecord.created_at.desc())
                .offset(offset)
                .limit(limit)
                .all()
            )


# 全局单例
database_manager = DatabaseManager()
