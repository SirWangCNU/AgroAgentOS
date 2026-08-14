"""农场和地块 API 路由."""

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.farm import (
    FarmCreateRequest,
    FarmDetail,
    FarmInfo,
    FarmListResponse,
    FarmUpdateRequest,
    FieldCreateRequest,
    FieldInfo,
    FieldListResponse,
    FieldUpdateRequest,
)
from app.schemas.weather import FarmWeatherSummary
from app.services import farm_service
from app.services.weather_service import get_farm_weather_summary, get_field_weather_summary

router = APIRouter(tags=["农场管理"])


# ==================== 农场接口 ====================


@router.post("/farms", response_model=ApiResponse[FarmInfo])
def create_farm(
    req: FarmCreateRequest,
    current_user: User = Depends(get_current_user),
) -> ApiResponse:
    """创建农场."""
    farm = farm_service.create_farm(current_user.id, req)
    info = FarmInfo.model_validate(farm)
    return ApiResponse.success(data=info, message="农场创建成功")


@router.get("/farms", response_model=ApiResponse[FarmListResponse])
def list_farms(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    current_user: User = Depends(get_current_user),
) -> ApiResponse:
    """获取农场列表."""
    farms, total = farm_service.get_farms(current_user.id, page, page_size)
    items = []
    for f in farms:
        info = FarmInfo.model_validate(f)
        info.field_count = farm_service.get_field_count(f.id)
        items.append(info)
    return ApiResponse.success(data=FarmListResponse(total=total, farms=items))


@router.get("/farms/{farm_id}", response_model=ApiResponse[FarmDetail])
def get_farm(
    farm_id: int,
    current_user: User = Depends(get_current_user),
) -> ApiResponse:
    """获取农场详情 (含地块列表)."""
    farm = farm_service.get_farm(farm_id, current_user.id)
    fields = farm_service.get_fields(farm_id, current_user.id)
    detail = FarmDetail.model_validate(farm)
    detail.field_count = len(fields)
    detail.fields = [FieldInfo.model_validate(f) for f in fields]
    return ApiResponse.success(data=detail)


@router.get("/farms/{farm_id}/weather", response_model=ApiResponse[FarmWeatherSummary])
async def get_farm_weather(
    farm_id: int,
    current_user: User = Depends(get_current_user),
) -> ApiResponse:
    """获取当前用户指定农场的实时天气和风险摘要。"""
    farm = farm_service.get_farm(farm_id, current_user.id)
    summary = await get_farm_weather_summary(farm)
    return ApiResponse.success(data=summary, message="农场天气查询成功")


@router.put("/farms/{farm_id}", response_model=ApiResponse[FarmInfo])
def update_farm(
    farm_id: int,
    req: FarmUpdateRequest,
    current_user: User = Depends(get_current_user),
) -> ApiResponse:
    """更新农场."""
    farm = farm_service.update_farm(farm_id, current_user.id, req)
    return ApiResponse.success(data=FarmInfo.model_validate(farm), message="农场更新成功")


@router.delete("/farms/{farm_id}", response_model=ApiResponse)
def delete_farm(
    farm_id: int,
    current_user: User = Depends(get_current_user),
) -> ApiResponse:
    """删除农场 (级联删除地块)."""
    farm_service.delete_farm(farm_id, current_user.id)
    return ApiResponse.success(message="农场已删除")


# ==================== 地块接口 ====================


@router.post("/farms/{farm_id}/fields", response_model=ApiResponse[FieldInfo])
def create_field(
    farm_id: int,
    req: FieldCreateRequest,
    current_user: User = Depends(get_current_user),
) -> ApiResponse:
    """在农场下创建地块."""
    field = farm_service.create_field(farm_id, current_user.id, req)
    return ApiResponse.success(data=FieldInfo.model_validate(field), message="地块创建成功")


@router.get("/farms/{farm_id}/fields", response_model=ApiResponse[FieldListResponse])
def list_fields(
    farm_id: int,
    current_user: User = Depends(get_current_user),
) -> ApiResponse:
    """获取农场的所有地块."""
    fields = farm_service.get_fields(farm_id, current_user.id)
    items = [FieldInfo.model_validate(f) for f in fields]
    return ApiResponse.success(data=FieldListResponse(total=len(items), fields=items))


@router.get("/fields/{field_id}", response_model=ApiResponse[FieldInfo])
def get_field(
    field_id: int,
    current_user: User = Depends(get_current_user),
) -> ApiResponse:
    """获取地块详情."""
    field = farm_service.get_field(field_id, current_user.id)
    return ApiResponse.success(data=FieldInfo.model_validate(field))


@router.get("/fields/{field_id}/weather", response_model=ApiResponse[FarmWeatherSummary])
async def get_field_weather(
    field_id: int,
    current_user: User = Depends(get_current_user),
) -> ApiResponse:
    """获取当前用户指定地块的实时天气、三日趋势和风险摘要。"""
    field = farm_service.get_field(field_id, current_user.id)
    farm = farm_service.get_farm(field.farm_id, current_user.id)
    summary = await get_field_weather_summary(field, location_hint=farm.location or "")
    return ApiResponse.success(data=summary, message="地块天气查询成功")


@router.put("/fields/{field_id}", response_model=ApiResponse[FieldInfo])
def update_field(
    field_id: int,
    req: FieldUpdateRequest,
    current_user: User = Depends(get_current_user),
) -> ApiResponse:
    """更新地块."""
    field = farm_service.update_field(field_id, current_user.id, req)
    return ApiResponse.success(data=FieldInfo.model_validate(field), message="地块更新成功")


@router.delete("/fields/{field_id}", response_model=ApiResponse)
def delete_field(
    field_id: int,
    current_user: User = Depends(get_current_user),
) -> ApiResponse:
    """删除地块."""
    farm_service.delete_field(field_id, current_user.id)
    return ApiResponse.success(message="地块已删除")
