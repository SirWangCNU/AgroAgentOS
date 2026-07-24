"""农场和地块业务服务."""

from typing import Optional

from loguru import logger

from app.core.sqlite import sqlite_manager
from app.exceptions import AppException
from app.models.farm import Farm, Field
from app.schemas.farm import (
    FarmCreateRequest,
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
