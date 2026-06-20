"""位置服务 - 从用户农场获取当前位置.

设计:
  - 优先从用户 Farm 表取 location/latitude/longitude
  - 无 Farm 时回退到 DEFAULT_LOCATION (北京)
  - 供 API 层和工具层共用, 避免重复查询

参考: app/services/farm_service.py 的 SQLite 会话模式.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from loguru import logger

from app.core.sqlite import sqlite_manager
from app.models.farm import Farm


# 默认位置 (无 Farm 时回退)
DEFAULT_LOCATION = "北京"


@dataclass
class UserLocation:
    """用户位置信息."""
    location: str          # 城市名 (如 "北京"/"山东寿光")
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    source: str = "farm"   # farm / default


def get_user_location(user_id: Optional[int]) -> UserLocation:
    """获取用户位置.

    优先取用户第一个农场的 location, 无农场回退 DEFAULT_LOCATION.

    Args:
        user_id: 用户 ID, None 或不存在时回退默认

    Returns:
        UserLocation, source 标识来源
    """
    if not user_id:
        return UserLocation(location=DEFAULT_LOCATION, source="default")

    try:
        with sqlite_manager.session() as sess:
            # 取用户第一个农场 (按创建时间最早)
            farm = (
                sess.query(Farm)
                .filter(Farm.user_id == user_id)
                .order_by(Farm.created_at.asc())
                .first()
            )
            if farm and farm.location:
                loc = UserLocation(
                    location=farm.location,
                    latitude=farm.latitude,
                    longitude=farm.longitude,
                    source="farm",
                )
                logger.debug(
                    f"[Location] user={user_id} location={loc.location} "
                    f"lat={loc.latitude} lon={loc.longitude}"
                )
                return loc
    except Exception as e:
        logger.warning(f"[Location] 查询用户农场失败, 回退默认: {e}")

    return UserLocation(location=DEFAULT_LOCATION, source="default")


def resolve_location(location: Optional[str], user_id: Optional[int] = None) -> str:
    """解析位置: 显式传入优先, 否则从用户农场取, 再回退默认.

    供 API 端点用: 当 query 参数 location 为空时自动从用户农场补全.

    Args:
        location: 显式传入的位置 (可能为空)
        user_id: 用户 ID

    Returns:
        解析后的位置字符串
    """
    if location and location.strip():
        return location.strip()
    return get_user_location(user_id).location
