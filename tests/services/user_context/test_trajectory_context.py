"""轨迹作业数据上下文构建单元测试."""

from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.sqlite import Base
from app.models.farm import Farm, Field
from app.models.trajectory import TrajectoryFile
from app.services.user_context.trajectory_context import build_trajectory_context


@pytest.fixture
def db_session():
    """创建内存 SQLite 会话."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def _create_test_data(db_session, user_id=1, days_ago=1):
    """创建测试用的农场、地块和轨迹数据."""
    farm = Farm(user_id=user_id, name="测试农场", area_mu=50.0)
    db_session.add(farm)
    db_session.flush()

    field = Field(farm_id=farm.id, name="A1地块", area_mu=30.0, current_crop="小麦")
    db_session.add(field)
    db_session.flush()

    traj = TrajectoryFile(
        field_id=field.id,
        filename="test_trajectory.xlsx",
        machine_id="JD-1001",
        point_count=500,
        start_time=datetime.now() - timedelta(days=days_ago),
        end_time=datetime.now() - timedelta(days=days_ago, hours=-2),
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
    return traj


class TestBuildTrajectoryContext:
    """轨迹上下文构建."""

    def test_no_data(self, db_session):
        result = build_trajectory_context(db_session, user_id=1)
        assert result == ""

    def test_basic_trajectory(self, db_session):
        _create_test_data(db_session)

        result = build_trajectory_context(db_session, user_id=1)
        assert "近期作业数据" in result
        assert "测试农场" in result
        assert "A1地块" in result
        assert "test_trajectory.xlsx" in result
        assert "JD-1001" in result
        assert "18.2cm" in result
        assert "4.2km/h" in result
        assert "28.5亩" in result
        assert "2.1cm" in result  # 标准差

    def test_time_range_recent(self, db_session):
        """测试最近7天过滤."""
        _create_test_data(db_session, days_ago=1)
        _create_test_data(db_session, days_ago=10)  # 超过7天

        # recent 应只包含最近7天的
        result = build_trajectory_context(db_session, user_id=1, time_range="recent")
        # 应该有数据（1天前的那条）
        assert "近期作业数据" in result

    def test_user_isolation(self, db_session):
        """不同用户数据隔离."""
        _create_test_data(db_session, user_id=1)

        result = build_trajectory_context(db_session, user_id=999)
        assert result == ""

    def test_multiple_trajectories(self, db_session):
        """多条轨迹记录."""
        farm = Farm(user_id=1, name="测试农场", area_mu=50.0)
        db_session.add(farm)
        db_session.flush()

        field = Field(farm_id=farm.id, name="A1地块", area_mu=30.0)
        db_session.add(field)
        db_session.flush()

        for i in range(3):
            traj = TrajectoryFile(
                field_id=field.id,
                filename=f"traj_{i}.xlsx",
                machine_id=f"JD-{1000+i}",
                point_count=100,
                start_time=datetime.now() - timedelta(days=i),
                work_area_mu=10.0 + i,
                avg_depth=15.0 + i,
                avg_speed=4.0,
                depth_std=1.5,
                work_distance_m=3000.0,
                total_distance_m=4000.0,
                work_width=2.0,
            )
            db_session.add(traj)
        db_session.commit()

        result = build_trajectory_context(db_session, user_id=1, limit=2)
        assert "traj_0" in result  # 最新的
        assert "traj_1" in result  # 次新的
        assert "traj_2" not in result  # 被 limit 截断

    def test_zero_stats_not_shown(self, db_session):
        """统计值为0时不显示."""
        farm = Farm(user_id=1, name="测试农场", area_mu=50.0)
        db_session.add(farm)
        db_session.flush()

        field = Field(farm_id=farm.id, name="A1地块", area_mu=30.0)
        db_session.add(field)
        db_session.flush()

        traj = TrajectoryFile(
            field_id=field.id,
            filename="empty_stats.xlsx",
            machine_id="",
            point_count=10,
            start_time=datetime.now(),
            work_area_mu=0.0,
            avg_depth=0.0,
            avg_speed=0.0,
            depth_std=0.0,
            work_distance_m=0.0,
            total_distance_m=0.0,
        )
        db_session.add(traj)
        db_session.commit()

        result = build_trajectory_context(db_session, user_id=1)
        assert "empty_stats.xlsx" in result
        # 0 值不应出现在统计中
        assert "0.0亩" not in result
        assert "0.0cm" not in result
