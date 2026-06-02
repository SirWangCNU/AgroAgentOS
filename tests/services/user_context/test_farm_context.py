"""农场上下文构建单元测试.

使用内存 SQLite 数据库模拟真实数据.
"""

from datetime import date, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.sqlite import Base
from app.models.farm import Farm, Field
from app.services.user_context.farm_context import build_farm_summary


@pytest.fixture
def db_session():
    """创建内存 SQLite 会话."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


class TestBuildFarmSummary:
    """农场摘要构建."""

    def test_no_farms(self, db_session):
        result = build_farm_summary(db_session, user_id=1)
        assert result == ""

    def test_single_farm_no_fields(self, db_session):
        farm = Farm(user_id=1, name="阳光农场", location="山东寿光", area_mu=50.0)
        db_session.add(farm)
        db_session.commit()

        result = build_farm_summary(db_session, user_id=1)
        assert "阳光农场" in result
        assert "山东寿光" in result
        assert "50亩" in result
        assert "暂无地块" in result

    def test_farm_with_fields(self, db_session):
        farm = Farm(user_id=1, name="阳光农场", location="山东寿光", area_mu=50.0)
        db_session.add(farm)
        db_session.flush()

        field1 = Field(
            farm_id=farm.id, name="A1地块", area_mu=30.0,
            soil_type="壤土", current_crop="小麦", growth_stage="播种期",
            status="planting",
        )
        field2 = Field(
            farm_id=farm.id, name="A2地块", area_mu=20.0,
            soil_type="黏土", current_crop="玉米", growth_stage="生长期",
            status="planting",
        )
        db_session.add_all([field1, field2])
        db_session.commit()

        result = build_farm_summary(db_session, user_id=1)
        assert "阳光农场" in result
        assert "A1地块" in result
        assert "小麦" in result
        assert "播种期" in result
        assert "壤土" in result
        assert "A2地块" in result
        assert "玉米" in result
        assert "2 个地块" in result

    def test_multiple_farms(self, db_session):
        farm1 = Farm(user_id=1, name="农场A", location="山东", area_mu=30.0)
        farm2 = Farm(user_id=1, name="农场B", location="河南", area_mu=50.0)
        db_session.add_all([farm1, farm2])
        db_session.commit()

        result = build_farm_summary(db_session, user_id=1)
        assert "2 个农场" in result
        assert "农场A" in result
        assert "农场B" in result
        assert "80亩" in result  # 总面积

    def test_user_isolation(self, db_session):
        """不同用户数据隔离."""
        farm1 = Farm(user_id=1, name="用户1的农场", area_mu=10.0)
        farm2 = Farm(user_id=2, name="用户2的农场", area_mu=20.0)
        db_session.add_all([farm1, farm2])
        db_session.commit()

        result = build_farm_summary(db_session, user_id=1)
        assert "用户1的农场" in result
        assert "用户2的农场" not in result

    def test_fallow_field(self, db_session):
        farm = Farm(user_id=1, name="测试农场", area_mu=10.0)
        db_session.add(farm)
        db_session.flush()

        field = Field(farm_id=farm.id, name="A1地块", status="fallow")
        db_session.add(field)
        db_session.commit()

        result = build_farm_summary(db_session, user_id=1)
        assert "休耕" in result
