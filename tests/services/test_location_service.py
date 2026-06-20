"""location_service 单元测试.

覆盖:
  - 无 user_id 回退默认
  - 有农场返回农场位置
  - 无农场回退默认
  - resolve_location 显式传入优先
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.sqlite import Base
from app.models.farm import Farm
from app.services.location_service import (
    DEFAULT_LOCATION,
    UserLocation,
    get_user_location,
    resolve_location,
)


@pytest.fixture
def db_session():
    """内存 SQLite 会话."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


class TestGetUserLocation:
    """get_user_location."""

    def test_no_user_id_returns_default(self):
        """无 user_id 回退默认."""
        result = get_user_location(None)
        assert result.location == DEFAULT_LOCATION
        assert result.source == "default"

    def test_no_farm_returns_default(self, db_session):
        """有 user_id 但无农场, 回退默认."""
        with patch("app.services.location_service.sqlite_manager") as mock_mgr:
            mock_mgr.session.return_value.__enter__.return_value = db_session
            mock_mgr.session.return_value.__exit__.return_value = None
            result = get_user_location(user_id=999)
        assert result.location == DEFAULT_LOCATION
        assert result.source == "default"

    def test_farm_with_location(self, db_session):
        """有农场返回农场位置."""
        farm = Farm(
            user_id=1, name="阳光农场", location="山东寿光",
            latitude=36.85, longitude=118.74, area_mu=50.0,
        )
        db_session.add(farm)
        db_session.commit()

        with patch("app.services.location_service.sqlite_manager") as mock_mgr:
            mock_mgr.session.return_value.__enter__.return_value = db_session
            mock_mgr.session.return_value.__exit__.return_value = None
            result = get_user_location(user_id=1)
        assert result.location == "山东寿光"
        assert result.latitude == 36.85
        assert result.longitude == 118.74
        assert result.source == "farm"

    def test_farm_empty_location_returns_default(self, db_session):
        """农场 location 为空, 回退默认."""
        farm = Farm(user_id=1, name="空位置农场", location="", area_mu=10.0)
        db_session.add(farm)
        db_session.commit()

        with patch("app.services.location_service.sqlite_manager") as mock_mgr:
            mock_mgr.session.return_value.__enter__.return_value = db_session
            mock_mgr.session.return_value.__exit__.return_value = None
            result = get_user_location(user_id=1)
        assert result.location == DEFAULT_LOCATION
        assert result.source == "default"

    def test_multiple_farms_returns_earliest(self, db_session):
        """多个农场返回最早创建的."""
        farm1 = Farm(user_id=1, name="农场A", location="山东", area_mu=10.0)
        db_session.add(farm1)
        db_session.commit()

        farm2 = Farm(user_id=1, name="农场B", location="河南", area_mu=20.0)
        db_session.add(farm2)
        db_session.commit()

        with patch("app.services.location_service.sqlite_manager") as mock_mgr:
            mock_mgr.session.return_value.__enter__.return_value = db_session
            mock_mgr.session.return_value.__exit__.return_value = None
            result = get_user_location(user_id=1)
        # 最早创建的是农场A
        assert result.location == "山东"


class TestResolveLocation:
    """resolve_location."""

    def test_explicit_location_wins(self):
        """显式传入优先."""
        result = resolve_location("上海", user_id=1)
        assert result == "上海"

    def test_empty_location_uses_default(self):
        """空位置回退默认."""
        result = resolve_location(None, user_id=None)
        assert result == DEFAULT_LOCATION

    def test_whitespace_location_uses_default(self):
        """纯空格位置回退默认."""
        result = resolve_location("   ", user_id=None)
        assert result == DEFAULT_LOCATION

    def test_empty_with_farm_uses_farm(self, db_session):
        """空位置 + 有农场 → 用农场位置."""
        farm = Farm(user_id=1, name="农场", location="山东寿光", area_mu=10.0)
        db_session.add(farm)
        db_session.commit()

        with patch("app.services.location_service.sqlite_manager") as mock_mgr:
            mock_mgr.session.return_value.__enter__.return_value = db_session
            mock_mgr.session.return_value.__exit__.return_value = None
            result = resolve_location(None, user_id=1)
        assert result == "山东寿光"
