"""会话 ORM 只应向 SQLAlchemy 注册一次。"""

from sqlalchemy import create_engine


def test_session_schema_creates_once_after_session_service_import():
    """防止两个 ChatSession 定义生成重名 SQLite 索引。"""
    import app.services.session_service  # noqa: F401
    from app.core.sqlite import Base

    engine = create_engine("sqlite:///:memory:")
    try:
        Base.metadata.create_all(engine)
    finally:
        engine.dispose()
