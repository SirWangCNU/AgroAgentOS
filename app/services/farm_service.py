"""农场和地块业务服务."""

from datetime import datetime, timezone
from typing import Optional

from loguru import logger

from app.core.sqlite import sqlite_manager
from app.exceptions import AppException
from app.models.farm import CropSeason, Farm, Field
from app.models.farm_agent import FarmEvent
from app.schemas.farm import (
    CropSeasonCreateRequest,
    CropSeasonUpdateRequest,
    FarmCreateRequest,
    FarmEventCreateRequest,
    FarmUpdateRequest,
    FieldCreateRequest,
    FieldUpdateRequest,
)


# ==================== 农场 CRUD ====================


def create_farm(user_id: int, data: FarmCreateRequest) -> Farm:
    """创建农场."""
    with sqlite_manager.session() as sess:
        farm = Farm(
            user_id=user_id,
            name=data.name,
            location=data.location,
            latitude=data.latitude,
            longitude=data.longitude,
            area_mu=data.area_mu or 0.0,
            description=data.description,
        )
        sess.add(farm)
        sess.flush()
        farm_id = farm.id
        sess.expunge(farm)
        logger.info(f"[Farm] 创建农场: id={farm_id} user={user_id} name={data.name}")
        return farm


def get_farms(user_id: int, page: int = 1, page_size: int = 20) -> tuple[list[Farm], int]:
    """获取用户的农场列表 (分页)."""
    with sqlite_manager.session() as sess:
        query = sess.query(Farm).filter(Farm.user_id == user_id)
        total = query.count()
        farms = (
            query.order_by(Farm.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        for f in farms:
            sess.expunge(f)
        return farms, total


def get_farm(farm_id: int, user_id: int) -> Farm:
    """获取农场详情."""
    with sqlite_manager.session() as sess:
        farm = sess.query(Farm).filter(Farm.id == farm_id, Farm.user_id == user_id).first()
        if not farm:
            raise AppException(status_code=404, detail="农场不存在")
        sess.expunge(farm)
        return farm


def update_farm(farm_id: int, user_id: int, data: FarmUpdateRequest) -> Farm:
    """更新农场."""
    with sqlite_manager.session() as sess:
        farm = sess.query(Farm).filter(Farm.id == farm_id, Farm.user_id == user_id).first()
        if not farm:
            raise AppException(status_code=404, detail="农场不存在")
        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(farm, key, value)
        sess.flush()
        sess.expunge(farm)
        logger.info(f"[Farm] 更新农场: id={farm_id} fields={list(update_data.keys())}")
        return farm


def delete_farm(farm_id: int, user_id: int) -> None:
    """删除农场 (级联删除地块)."""
    with sqlite_manager.session() as sess:
        farm = sess.query(Farm).filter(Farm.id == farm_id, Farm.user_id == user_id).first()
        if not farm:
            raise AppException(status_code=404, detail="农场不存在")
        # 先删除关联地块
        sess.query(Field).filter(Field.farm_id == farm_id).delete()
        sess.delete(farm)
        logger.info(f"[Farm] 删除农场: id={farm_id}")


def get_field_count(farm_id: int) -> int:
    """获取农场的地块数量."""
    with sqlite_manager.session() as sess:
        return sess.query(Field).filter(Field.farm_id == farm_id).count()


# ==================== 地块 CRUD ====================


def create_field(farm_id: int, user_id: int, data: FieldCreateRequest) -> Field:
    """创建地块."""
    # 验证农场存在且属于当前用户
    get_farm(farm_id, user_id)
    with sqlite_manager.session() as sess:
        field = Field(
            farm_id=farm_id,
            name=data.name,
            area_mu=data.area_mu or 0.0,
            soil_type=data.soil_type,
            current_crop=data.current_crop,
            planting_date=data.planting_date,
            expected_harvest=data.expected_harvest,
            growth_stage=data.growth_stage,
            status=data.status,
            latitude=data.latitude,
            longitude=data.longitude,
            notes=data.notes,
            boundary_json=data.boundary_json,
        )
        sess.add(field)
        sess.flush()
        field_id = field.id
        sess.expunge(field)
        logger.info(f"[Field] 创建地块: id={field_id} farm={farm_id} name={data.name}")
        return field


def get_fields(farm_id: int, user_id: int) -> list[Field]:
    """获取农场的所有地块."""
    get_farm(farm_id, user_id)
    with sqlite_manager.session() as sess:
        fields = (
            sess.query(Field)
            .filter(Field.farm_id == farm_id)
            .order_by(Field.created_at.desc())
            .all()
        )
        for f in fields:
            sess.expunge(f)
        return fields


def get_field(field_id: int, user_id: int) -> Field:
    """获取地块详情."""
    with sqlite_manager.session() as sess:
        field = sess.query(Field).filter(Field.id == field_id).first()
        if not field:
            raise AppException(status_code=404, detail="地块不存在")
        # 验证所属农场属于当前用户
        farm = sess.query(Farm).filter(Farm.id == field.farm_id, Farm.user_id == user_id).first()
        if not farm:
            raise AppException(status_code=403, detail="无权访问该地块")
        sess.expunge(field)
        return field


def update_field(field_id: int, user_id: int, data: FieldUpdateRequest) -> Field:
    """更新地块."""
    with sqlite_manager.session() as sess:
        field = sess.query(Field).filter(Field.id == field_id).first()
        if not field:
            raise AppException(status_code=404, detail="地块不存在")
        farm = sess.query(Farm).filter(Farm.id == field.farm_id, Farm.user_id == user_id).first()
        if not farm:
            raise AppException(status_code=403, detail="无权修改该地块")
        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(field, key, value)
        sess.flush()
        sess.expunge(field)
        logger.info(f"[Field] 更新地块: id={field_id} fields={list(update_data.keys())}")
        return field


def delete_field(field_id: int, user_id: int) -> None:
    """删除地块."""
    with sqlite_manager.session() as sess:
        field = sess.query(Field).filter(Field.id == field_id).first()
        if not field:
            raise AppException(status_code=404, detail="地块不存在")
        farm = sess.query(Farm).filter(Farm.id == field.farm_id, Farm.user_id == user_id).first()
        if not farm:
            raise AppException(status_code=403, detail="无权删除该地块")
        sess.delete(field)
        logger.info(f"[Field] 删除地块: id={field_id}")


# ==================== 茬次与农事事件 ====================


def _require_owned_field(session, *, field_id: int, user_id: int) -> Field:
    field = session.query(Field).filter(Field.id == field_id).first()
    if not field:
        raise AppException(status_code=404, detail="地块不存在")
    farm = session.query(Farm).filter(
        Farm.id == field.farm_id,
        Farm.user_id == user_id,
    ).first()
    if not farm:
        raise AppException(status_code=403, detail="无权访问该地块")
    return field


def _sync_field_from_active_season(field: Field, season: CropSeason) -> None:
    if season.status != "growing":
        return
    field.current_season_id = season.id
    field.current_crop = season.crop_name
    field.growth_stage = season.current_stage
    field.planting_date = season.start_date
    field.expected_harvest = season.expected_harvest
    field.area_mu = season.area_mu or field.area_mu
    field.status = "planting"


def create_crop_season(
    *,
    field_id: int,
    user_id: int,
    data: CropSeasonCreateRequest,
) -> CropSeason:
    """创建地块茬次，并在 growing 状态时更新地块当前茬次指针."""
    with sqlite_manager.session() as sess:
        field = _require_owned_field(sess, field_id=field_id, user_id=user_id)
        season = CropSeason(
            field_id=field_id,
            crop_name=data.crop_name,
            variety=data.variety,
            season_code=data.season_code,
            start_date=data.start_date,
            expected_harvest=data.expected_harvest,
            current_stage=data.current_stage,
            area_mu=data.area_mu,
            target_yield=data.target_yield,
            status=data.status,
            note=data.note,
        )
        sess.add(season)
        sess.flush()
        _sync_field_from_active_season(field, season)
        sess.flush()
        sess.expunge(season)
        return season


def update_crop_season(
    *,
    season_id: int,
    user_id: int,
    data: CropSeasonUpdateRequest,
) -> CropSeason:
    """更新茬次，并在 growing 状态时同步地块当前作物字段."""
    with sqlite_manager.session() as sess:
        season = sess.query(CropSeason).filter(CropSeason.id == season_id).first()
        if not season:
            raise AppException(status_code=404, detail="茬次不存在")
        field = _require_owned_field(sess, field_id=season.field_id, user_id=user_id)
        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(season, key, value)
        _sync_field_from_active_season(field, season)
        sess.flush()
        sess.expunge(season)
        return season


def close_crop_season(
    *,
    season_id: int,
    user_id: int,
    status: str = "harvested",
) -> CropSeason:
    """结束当前茬次，默认标记为 harvested."""
    with sqlite_manager.session() as sess:
        season = sess.query(CropSeason).filter(CropSeason.id == season_id).first()
        if not season:
            raise AppException(status_code=404, detail="茬次不存在")
        field = _require_owned_field(sess, field_id=season.field_id, user_id=user_id)
        season.status = status
        if field.current_season_id == season.id:
            field.current_season_id = None
            field.status = "fallow"
        sess.flush()
        sess.expunge(season)
        return season


def create_farm_event(
    *,
    field_id: int,
    user_id: int,
    data: FarmEventCreateRequest,
) -> FarmEvent:
    """人工记录一条农事事件."""
    with sqlite_manager.session() as sess:
        field = _require_owned_field(sess, field_id=field_id, user_id=user_id)
        if data.season_id is not None:
            season = sess.query(CropSeason).filter(
                CropSeason.id == data.season_id,
                CropSeason.field_id == field_id,
            ).first()
            if season is None:
                raise AppException(status_code=403, detail="无权访问目标茬次")
        event = FarmEvent(
            field_id=field_id,
            season_id=data.season_id or field.current_season_id,
            event_type=data.event_type,
            event_time=data.event_time or datetime.now(timezone.utc),
            operator=data.operator or f"user:{user_id}",
            source="human_entry",
            note=data.note,
        )
        event.set_inputs(data.inputs)
        event.set_geo_payload(data.geo_payload)
        event.set_evidence(data.evidence)
        sess.add(event)
        sess.flush()
        sess.expunge(event)
        return event
