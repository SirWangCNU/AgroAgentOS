"""UserContextService 集成测试."""

from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.sqlite import Base
from app.models.farm import Farm, Field
from app.models.trajectory import TrajectoryFile
from app.services.user_context.service import UserContextService, get_user_context


@pytest.fixture
def db_session():
    """创建内存 SQLite 会话."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def _setup_full_data(db_session):
    """创建完整的测试数据."""
    farm = Farm(user_id=1, name="阳光农场", location="山东寿光", area_mu=50.0)
    db_session.add(farm)
    db_session.flush()

    field = Field(
        farm_id=farm.id, name="A1地块", area_mu=30.0,
        soil_type="壤土", current_crop="小麦", growth_stage="播种期",
        status="planting",
    )
    db_session.add(field)
    db_session.flush()

    traj = TrajectoryFile(
        field_id=field.id,
        filename="旋耕作业.xlsx",
        machine_id="JD-1001",
        point_count=500,
        start_time=datetime(2026, 5, 28),
        end_time=datetime(2026, 5, 28, 2),
        total_distance_m=5000.0,
        work_distance_m=4500.0,
        work_area_mu=28.5,
        avg_depth=18.2,
        avg_speed=4.2,
        depth_std=2.1,
        work_width=2.0,
    )
    db_session.add(traj)
    db_session.commit()


class TestUserContextService:
    """UserContextService 测试."""

    def test_no_data(self, db_session):
        svc = UserContextService(db_session, user_id=1)
        result = svc.get_context("你好")
        # 无数据时默认注入农场概况, 但没有农场所以为空
        assert result == ""

    def test_farm_context_injected_by_default(self, db_session):
        _setup_full_data(db_session)

        svc = UserContextService(db_session, user_id=1)
        result = svc.get_context("你好")
        assert "阳光农场" in result
        assert "A1地块" in result
        assert "小麦" in result

    def test_trajectory_context_on_demand(self, db_session):
        _setup_full_data(db_session)

        svc = UserContextService(db_session, user_id=1)
        result = svc.get_context("A1地块最近作业质量怎么样")
        assert "近期作业数据" in result
        assert "18.2cm" in result
        assert "旋耕作业.xlsx" in result

    def test_farm_and_trajectory_combined(self, db_session):
        _setup_full_data(db_session)

        svc = UserContextService(db_session, user_id=1)
        result = svc.get_context("我农场A1地块的旋耕深度合适吗")
        # 应同时包含农场和轨迹数据
        assert "阳光农场" in result
        assert "近期作业数据" in result

    def test_context_truncation(self, db_session):
        """超长上下文截断."""
        # 创建大量农场数据
        for i in range(50):
            farm = Farm(user_id=1, name=f"农场{i}" * 20, location="测试地点" * 10, area_mu=100.0)
            db_session.add(farm)
            db_session.flush()
            for j in range(5):
                field = Field(
                    farm_id=farm.id, name=f"地块{j}" * 10,
                    current_crop="小麦" * 5, soil_type="壤土",
                )
                db_session.add(field)
        db_session.commit()

        svc = UserContextService(db_session, user_id=1)
        result = svc.get_context("我种了什么")
        assert len(result) <= 6000 + 20  # 允许截断提示的长度


class TestGetUserContext:
    """便捷函数测试."""

    def test_convenience_function(self, db_session):
        _setup_full_data(db_session)

        result = get_user_context(db_session, user_id=1, query="我的农场")
        assert "阳光农场" in result

    def test_no_data_returns_empty(self, db_session):
        result = get_user_context(db_session, user_id=999, query="我的农场")
        assert result == ""
