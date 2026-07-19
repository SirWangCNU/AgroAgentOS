"""农场和地块 ORM 模型."""

import json
from typing import Any

from sqlalchemy import Column, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func

from app.core.sqlite import Base


class Farm(Base):
    """农场表."""

    __tablename__ = "farms"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(128), nullable=False)
    location = Column(String(256), default="")
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    area_mu = Column(Float, default=0.0)  # 面积/亩
    description = Column(Text, default="")
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())


class Field(Base):
    """地块表."""

    __tablename__ = "fields"

    id = Column(Integer, primary_key=True, autoincrement=True)
    farm_id = Column(Integer, ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(128), nullable=False)
    area_mu = Column(Float, default=0.0)
    soil_type = Column(String(64), default="")  # 沙土/黏土/壤土
    current_crop = Column(String(64), default="")
    planting_date = Column(Date, nullable=True)
    expected_harvest = Column(Date, nullable=True)
    growth_stage = Column(String(64), default="")  # 生长阶段
    status = Column(String(32), default="idle")  # idle/planting/fallow
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    notes = Column(Text, default="")
    boundary_json = Column(Text, default="")  # 地块边界 GeoJSON
    current_season_id = Column(
        Integer,
        ForeignKey("crop_seasons.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )  # 当前茬次指针，由 CropSeason 开启/结束时维护
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())


class CropSeason(Base):
    """茬次表 - 记录每个地块的一次作物种植周期.

    一个 Field 可以有多个历史 CropSeason，但只有一个 current_season_id 指针指向当前茬次。
    AI 巡检时通过茬次知道"第几茬、第几天、当前生育期"，决策才有时间轴。
    """

    __tablename__ = "crop_seasons"

    id = Column(Integer, primary_key=True, autoincrement=True)
    field_id = Column(
        Integer,
        ForeignKey("fields.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    crop_name = Column(String(64), nullable=False)  # 水稻/玉米/大豆...
    variety = Column(String(128), nullable=False, default="")  # 品种
    season_code = Column(String(32), nullable=False)  # 2026-S1 / 2026秋
    start_date = Column(Date, nullable=False)  # 播种/定植日
    expected_harvest = Column(Date, nullable=True)
    current_stage = Column(String(64), nullable=False, default="")  # 苗期/分蘖/拔节/抽穗/灌浆/成熟
    area_mu = Column(Float, nullable=False, default=0.0)
    target_yield = Column(String(64), nullable=False, default="")  # 目标产量（含单位）
    status = Column(
        String(16),
        nullable=False,
        default="planning",
        index=True,
    )  # planning/growing/harvested/aborted
    note = Column(Text, nullable=False, default="")
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())


class SensorReading(Base):
    """感知数据读数表 - 存储土壤/虫情/NDVI/长势等多源感知数据.

    比赛场景下由 demo_scenario_service 从 fixture 注入；
    未来接入真实 IoT 设备时同一张表存储，source 字段区分来源。
    farm_risk_service 通过 (field_id, sensor_type, observed_at) 查询最新读数生成风险。
    """

    __tablename__ = "sensor_readings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    field_id = Column(
        Integer,
        ForeignKey("fields.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sensor_type = Column(String(32), nullable=False, index=True)
    # soil_moisture / pest_count / ndvi / growth_stage / anomaly_image / soil_nitrogen
    value_float = Column(Float, nullable=True)  # 数值类读数（含水量%、虫口数、NDVI 0-1）
    value_json = Column(Text, nullable=False, default="{}")  # 结构化读数（图像识别结果、多维数据）
    unit = Column(String(32), nullable=False, default="")  # %, 头/灯, mg/kg, ...
    observed_at = Column(DateTime, nullable=False, index=True)  # 观测时间（非入库时间）
    source = Column(String(32), nullable=False, default="fixture", index=True)
    # fixture / demo_scenario / iot / manual
    scenario_id = Column(String(64), nullable=True, index=True)  # 来源场景ID（比赛注入时填）
    note = Column(Text, nullable=False, default="")
    created_at = Column(DateTime, nullable=False, default=func.now())

    __table_args__ = (
        # 比赛场景多次注入同一 (field, type, observed_at, scenario) 去重
        UniqueConstraint(
            "field_id",
            "sensor_type",
            "observed_at",
            "scenario_id",
            name="uq_sensor_reading_dedup",
        ),
    )

    @property
    def value(self) -> dict[str, Any]:
        if not self.value_json:
            return {}
        try:
            parsed = json.loads(self.value_json)
            if not isinstance(parsed, dict):
                return {}
            return parsed
        except (TypeError, ValueError, json.JSONDecodeError):
            return {}

    def set_value(self, data: dict[str, Any]) -> None:
        self.value_json = json.dumps(data, ensure_ascii=False)
