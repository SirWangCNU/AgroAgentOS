"""农场和地块业务服务."""

import json

from loguru import logger
from sqlalchemy.orm import Session

from app.core.sqlite import sqlite_manager
from app.exceptions import AppException
from app.models.farm import Farm, Field
from app.schemas.farm import (
    FarmCreateRequest,
    FarmUpdateRequest,
    FieldCreateRequest,
    FieldUpdateRequest,
)
from app.services.field_geometry import (
    OVERLAP_TOLERANCE_SQUARE_METERS,
    analyze_boundary,
    intersection_area_square_meters,
)


def _refresh_and_detach(sess: Session, instance):
    sess.refresh(instance)
    sess.expunge(instance)
    return instance


def _require_user_farm(sess: Session, farm_id: int, user_id: int, *, lock: bool = False) -> Farm:
    query = sess.query(Farm).filter(Farm.id == farm_id, Farm.user_id == user_id)
    if lock:
        query = query.with_for_update()
    farm = query.first()
    if not farm:
        raise AppException(status_code=404, detail="农场不存在")
    return farm


def _field_shape(field: Field):
    if not field.boundary_json:
        return None
    try:
        return analyze_boundary(json.loads(field.boundary_json)).shape
    except (TypeError, ValueError, AppException):
        return None


def _apply_boundary_to_field(field: Field, boundary: dict, existing_fields: list[Field]) -> None:
    geometry = analyze_boundary(boundary)
    for existing in existing_fields:
        if existing.id == field.id:
            continue
        existing_shape = _field_shape(existing)
        if existing_shape is None:
            continue
        overlap_area = intersection_area_square_meters(geometry.shape, existing_shape)
        if overlap_area > OVERLAP_TOLERANCE_SQUARE_METERS:
            raise AppException(
                "地块边界与已有地块重叠",
                code="FIELD_BOUNDARY_OVERLAP",
                status_code=409,
                detail={"overlap_square_meters": round(overlap_area, 2)},
            )
    field.boundary_json = json.dumps(geometry.normalized, ensure_ascii=False, separators=(",", ":"))
    field.area_mu = geometry.area_mu
    field.latitude = geometry.latitude
    field.longitude = geometry.longitude


def _recalculate_farm_area(sess: Session, farm: Farm) -> None:
    fields = sess.query(Field).filter(Field.farm_id == farm.id).all()
    farm.area_mu = round(sum((field.area_mu or 0.0) for field in fields), 4)


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
        _refresh_and_detach(sess, farm)
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
        _refresh_and_detach(sess, farm)
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
    with sqlite_manager.session() as sess:
        farm = _require_user_farm(sess, farm_id, user_id, lock=True)
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
        )
        if data.boundary is not None:
            existing_fields = sess.query(Field).filter(Field.farm_id == farm_id).all()
            _apply_boundary_to_field(field, data.boundary, existing_fields)
        sess.add(field)
        sess.flush()
        _recalculate_farm_area(sess, farm)
        sess.flush()
        field_id = field.id
        _refresh_and_detach(sess, field)
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
        farm = _require_user_farm(sess, field.farm_id, user_id, lock=True)
        update_data = data.model_dump(exclude_unset=True)
        boundary = update_data.pop("boundary", None)
        existing_boundary_json = field.boundary_json
        for key, value in update_data.items():
            if key in {"area_mu", "latitude", "longitude"} and (boundary is not None or existing_boundary_json):
                continue
            setattr(field, key, value)
        if boundary is not None:
            existing_fields = sess.query(Field).filter(Field.farm_id == farm.id).all()
            _apply_boundary_to_field(field, boundary, existing_fields)
        elif existing_boundary_json:
            _apply_boundary_to_field(field, json.loads(existing_boundary_json), [])
        sess.flush()
        _recalculate_farm_area(sess, farm)
        sess.flush()
        _refresh_and_detach(sess, field)
        logger.info(f"[Field] 更新地块: id={field_id} fields={list(update_data.keys())}")
        return field


def delete_field(field_id: int, user_id: int) -> None:
    """删除地块."""
    with sqlite_manager.session() as sess:
        field = sess.query(Field).filter(Field.id == field_id).first()
        if not field:
            raise AppException(status_code=404, detail="地块不存在")
        farm = _require_user_farm(sess, field.farm_id, user_id, lock=True)
        sess.delete(field)
        sess.flush()
        _recalculate_farm_area(sess, farm)
        logger.info(f"[Field] 删除地块: id={field_id}")
