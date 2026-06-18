"""天气相关数据模型.

定义天气预报、极端天气预警、节气提醒、种植历等数据结构。
"""

from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, Field


# ============================================================
# 天气预报 & 预警
# ============================================================

class WeatherAlert(BaseModel):
    """极端天气预警."""

    alert_type: str = Field(..., description="预警类型: 霜冻/暴雨/高温/干旱")
    date: str = Field(..., description="预警日期 (YYYY-MM-DD)")
    severity: str = Field(..., description="严重程度: 高/中/低")
    advice: str = Field(..., description="农事应对建议")


class DailyForecastDetail(BaseModel):
    """详细日预报 (支持 7 天)."""

    date: str = Field(..., description="日期 (YYYY-MM-DD)")
    min_temp: float = Field(..., description="最低温度 ℃")
    max_temp: float = Field(..., description="最高温度 ℃")
    precipitation_mm: float = Field(default=0.0, description="降水量 mm")
    condition: str = Field(default="多云", description="天气状况")
    wind_level: int = Field(default=0, description="风力等级")


class WeatherForecastResult(BaseModel):
    """天气预报 + 预警结果."""

    location: str = Field(default="", description="地点名称")
    daily: List[DailyForecastDetail] = Field(default_factory=list)
    alerts: List[WeatherAlert] = Field(default_factory=list)
    source: str = Field(default="mock", description="数据来源")


# ============================================================
# 节气提醒
# ============================================================

class SolarTermInfo(BaseModel):
    """节气信息."""

    term: str = Field(..., description="节气名称")
    date_range: str = Field(default="", description="大致日期范围")
    general_reminders: List[str] = Field(default_factory=list, description="通用农事提醒")
    crop_reminders: List[str] = Field(default_factory=list, description="特定作物提醒")


# ============================================================
# 种植历
# ============================================================

class CalendarStage(BaseModel):
    """种植历阶段."""

    name: str = Field(..., description="阶段名称")
    date: str = Field(..., description="日期 MM-DD")
    category: str = Field(..., description="类别: 播种/施肥/防虫/管理/收获")
    note: str = Field(default="", description="农事要点")


class PlantingCalendar(BaseModel):
    """全年种植历."""

    crop: str = Field(..., description="作物名称")
    zone: str = Field(..., description="气候分区")
    stages: List[CalendarStage] = Field(default_factory=list)
