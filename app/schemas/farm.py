"""农场和地块相关的 Pydantic 模型."""

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


# ==================== 请求模型 ====================


class FarmCreateRequest(BaseModel):
    """创建农场请求."""

    name: str = Field(..., min_length=1, max_length=128, description="农场名称")
    location: str = Field(default="", max_length=256, description="农场地址")
    latitude: Optional[float] = Field(None, description="纬度")
    longitude: Optional[float] = Field(None, description="经度")
    area_mu: Optional[float] = Field(None, ge=0, description="面积(亩)")
    description: str = Field(default="", description="描述")


class FarmUpdateRequest(BaseModel):
    """更新农场请求."""

    name: Optional[str] = Field(None, min_length=1, max_length=128, description="农场名称")
    location: Optional[str] = Field(None, max_length=256, description="农场地址")
    latitude: Optional[float] = Field(None, description="纬度")
    longitude: Optional[float] = Field(None, description="经度")
    area_mu: Optional[float] = Field(None, ge=0, description="面积(亩)")
    description: Optional[str] = Field(None, description="描述")


class FieldCreateRequest(BaseModel):
    """创建地块请求."""

    name: str = Field(..., min_length=1, max_length=128, description="地块名称")
    area_mu: Optional[float] = Field(None, ge=0, description="面积(亩)")
    soil_type: str = Field(default="", max_length=64, description="土壤类型: 沙土/黏土/壤土")
    current_crop: str = Field(default="", max_length=64, description="当前作物")
    planting_date: Optional[date] = Field(None, description="播种日期")
    expected_harvest: Optional[date] = Field(None, description="预计收获日期")
    growth_stage: str = Field(default="", max_length=64, description="生长阶段")
    status: str = Field(default="idle", description="状态: idle/planting/fallow")
    latitude: Optional[float] = Field(None, description="纬度")
    longitude: Optional[float] = Field(None, description="经度")
    notes: str = Field(default="", description="备注")


class FieldUpdateRequest(BaseModel):
    """更新地块请求."""

    name: Optional[str] = Field(None, min_length=1, max_length=128, description="地块名称")
    area_mu: Optional[float] = Field(None, ge=0, description="面积(亩)")
    soil_type: Optional[str] = Field(None, max_length=64, description="土壤类型")
    current_crop: Optional[str] = Field(None, max_length=64, description="当前作物")
    planting_date: Optional[date] = Field(None, description="播种日期")
    expected_harvest: Optional[date] = Field(None, description="预计收获日期")
    growth_stage: Optional[str] = Field(None, max_length=64, description="生长阶段")
    status: Optional[str] = Field(None, description="状态: idle/planting/fallow")
    latitude: Optional[float] = Field(None, description="纬度")
    longitude: Optional[float] = Field(None, description="经度")
    notes: Optional[str] = Field(None, description="备注")


# ==================== 响应模型 ====================


class FieldInfo(BaseModel):
    """地块信息."""

    id: int
    farm_id: int
    name: str
    area_mu: float
    soil_type: str
    current_crop: str
    planting_date: Optional[date]
    expected_harvest: Optional[date]
    growth_stage: str
    status: str
    latitude: Optional[float]
    longitude: Optional[float]
    notes: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FarmInfo(BaseModel):
    """农场信息."""

    id: int
    user_id: int
    name: str
    location: str
    latitude: Optional[float]
    longitude: Optional[float]
    area_mu: float
    description: str
    created_at: datetime
    updated_at: datetime
    field_count: int = Field(default=0, description="地块数量")

    model_config = ConfigDict(from_attributes=True)


class FarmDetail(FarmInfo):
    """农场详情 (含地块列表)."""

    fields: list[FieldInfo] = Field(default_factory=list, description="地块列表")


class FarmListResponse(BaseModel):
    """农场列表响应."""

    total: int
    farms: list[FarmInfo]


class FieldListResponse(BaseModel):
    """地块列表响应."""

    total: int
    fields: list[FieldInfo]
