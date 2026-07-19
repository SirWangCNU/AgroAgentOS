"""农场感知/事件/茬次的只读查询服务（B9 新增）.

职责:
  - list_sensor_readings: 按农场/地块/类型/天数查询 SensorReading
  - list_farm_events: 按农场/地块/天数查询 FarmEvent
  - list_crop_seasons: 按农场/地块/状态查询 CropSeason

设计:
  - 与 farm_run_query_service 一样是只读查询服务
  - 所有查询都先通过 _require_owned_farm 校验农场所有权
  - 返回 ORM 对象，由 router 层 model_validate 转 Response 模型
  - 不做 N+1 查询，单次会话内完成
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.core.sqlite import sqlite_manager
from app.exceptions import ForbiddenError
from app.models.farm import CropSeason, Farm, Field, SensorReading
from app.models.farm_agent import FarmEvent

_DEFAULT_SENSOR_DAYS = 7
_DEFAULT_EVENT_DAYS = 14
_MAX_DAYS = 365
_MAX_LIMIT = 200


def _require_owned_farm(session: Session, *, farm_id: int, user_id: int) -> Farm:
    """校验农场归属并返回 Farm 对象，与 farm_run_query_service 保持一致。"""
    farm = (
        session.query(Farm)
        .filter(Farm.id == farm_id, Farm.user_id == user_id)
        .first()
    )
    if farm is None:
        raise ForbiddenError(message="无权访问目标农场")
    return farm


def _resolve_field_ids(
    session: Session,
    *,
    farm_id: int,
    field_id: int | None,
) -> list[int]:
    """把 field_id 过滤条件解析为 field_ids 列表.

    - field_id=None: 返回该农场所有 field_id
    - field_id=<id>: 校验该 field 属于该农场，返回 [field_id]
    """
    if field_id is None:
        rows = (
            session.query(Field.id)
            .filter(Field.farm_id == farm_id)
            .order_by(Field.id.asc())
            .all()
        )
        return [row[0] for row in rows]

    owned = (
        session.query(Field.id)
        .filter(Field.id == field_id, Field.farm_id == farm_id)
        .first()
    )
    if owned is None:
        raise ForbiddenError(message="无权访问目标地块")
    return [field_id]


def _coerce_days(days: int | None, default: int) -> int:
    if days is None or days <= 0:
        return default
    return min(days, _MAX_DAYS)


def list_sensor_readings(
    *,
    user_id: int,
    farm_id: int,
    field_id: int | None = None,
    sensor_type: str | None = None,
    days: int | None = _DEFAULT_SENSOR_DAYS,
    limit: int = _MAX_LIMIT,
) -> list[SensorReading]:
    """按条件查询感知读数（最近 N 天，倒序）."""
    effective_days = _coerce_days(days, _DEFAULT_SENSOR_DAYS)
    cutoff = datetime.now(timezone.utc) - timedelta(days=effective_days)
    effective_limit = max(1, min(limit, _MAX_LIMIT))

    with sqlite_manager.session() as session:
        _require_owned_farm(session, farm_id=farm_id, user_id=user_id)
        field_ids = _resolve_field_ids(session, farm_id=farm_id, field_id=field_id)
        if not field_ids:
            return []

        query = session.query(SensorReading).filter(
            SensorReading.field_id.in_(field_ids),
            SensorReading.observed_at >= cutoff,
        )
        if sensor_type:
            query = query.filter(SensorReading.sensor_type == sensor_type)
        rows = (
            query.order_by(
                SensorReading.observed_at.desc(),
                SensorReading.id.desc(),
            )
            .limit(effective_limit)
            .all()
        )
        # expunge 让对象离开 session 后仍可访问
        for row in rows:
            session.expunge(row)
        return rows


def list_farm_events(
    *,
    user_id: int,
    farm_id: int,
    field_id: int | None = None,
    days: int | None = _DEFAULT_EVENT_DAYS,
    limit: int = _MAX_LIMIT,
) -> list[FarmEvent]:
    """按条件查询农场事件（最近 N 天，倒序）."""
    effective_days = _coerce_days(days, _DEFAULT_EVENT_DAYS)
    cutoff = datetime.now(timezone.utc) - timedelta(days=effective_days)
    effective_limit = max(1, min(limit, _MAX_LIMIT))

    with sqlite_manager.session() as session:
        _require_owned_farm(session, farm_id=farm_id, user_id=user_id)
        field_ids = _resolve_field_ids(session, farm_id=farm_id, field_id=field_id)
        if not field_ids:
            return []

        rows = (
            session.query(FarmEvent)
            .filter(
                FarmEvent.field_id.in_(field_ids),
                FarmEvent.event_time >= cutoff,
            )
            .order_by(FarmEvent.event_time.desc(), FarmEvent.id.desc())
            .limit(effective_limit)
            .all()
        )
        for row in rows:
            session.expunge(row)
        return rows


def list_crop_seasons(
    *,
    user_id: int,
    farm_id: int,
    field_id: int | None = None,
    status: str | None = None,
    limit: int = _MAX_LIMIT,
) -> list[CropSeason]:
    """按条件查询茬次（不限时间，按 start_date 倒序）."""
    effective_limit = max(1, min(limit, _MAX_LIMIT))

    with sqlite_manager.session() as session:
        _require_owned_farm(session, farm_id=farm_id, user_id=user_id)
        field_ids = _resolve_field_ids(session, farm_id=farm_id, field_id=field_id)
        if not field_ids:
            return []

        query = session.query(CropSeason).filter(
            CropSeason.field_id.in_(field_ids),
        )
        if status:
            query = query.filter(CropSeason.status == status)
        rows = (
            query.order_by(CropSeason.start_date.desc(), CropSeason.id.desc())
            .limit(effective_limit)
            .all()
        )
        for row in rows:
            session.expunge(row)
        return rows


def list_scenario_metas() -> list[Any]:
    """列出所有可用比赛场景的元信息（透传 demo_scenario_service）."""
    from app.services import demo_scenario_service

    return demo_scenario_service.list_scenarios()


def inject_scenario(
    *,
    user_id: int,
    farm_id: int,
    scenario_id: str,
) -> Any:
    """注入场景到农场（透传 demo_scenario_service）."""
    from app.services import demo_scenario_service

    return demo_scenario_service.inject_scenario_to_db(
        user_id=user_id,
        farm_id=farm_id,
        scenario_id=scenario_id,
    )
