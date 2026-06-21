"""天气 API 端点 - 供前端调用.

GET /api/v1/weather?location=北京          - 按城市名获取天气数据
GET /api/v1/weather/location?lat=xx&lon=xx - 按经纬度获取天气数据
GET /api/v1/weather/config                 - 获取天气页定位配置
"""

from __future__ import annotations

from fastapi import APIRouter, Query
from loguru import logger

from app.config import settings
from app.schemas.common import ApiResponse
from app.services.weather_service import get_weather_service

router = APIRouter(prefix="/weather", tags=["weather"])


def _weather_result_to_dict(result):
    """将 WeatherResult 转为前端期望的字典结构."""
    return {
        "current": {
            "location": result.current.location,
            "temperature": result.current.temperature,
            "humidity": result.current.humidity,
            "wind_speed": result.current.wind_speed,
            "wind_level": result.current.wind_level,
            "condition": result.current.condition,
            "rain_probability": result.current.rain_probability,
            "feels_like": result.current.feels_like,
            "pressure": result.current.pressure,
            "visibility": result.current.visibility,
            "uv_index": result.current.uv_index,
            "update_time": result.current.update_time,
        },
        "forecast": [
            {
                "date": d.date,
                "temp_high": d.temp_high,
                "temp_low": d.temp_low,
                "condition": d.condition,
                "rain_probability": d.rain_probability,
                "wind_level": d.wind_level,
            }
            for d in result.forecast
        ],
        "agriculture_advice": result.agriculture_advice,
        "source": result.source,
    }


@router.get(
    "",
    summary="获取天气数据",
    description="获取指定城市的实时天气、预报和农业建议",
)
async def get_weather(location: str = Query(default="北京", description="城市名称")):
    logger.info(f"[weather-api] 查询天气: {location}")
    service = get_weather_service()
    result = await service.get_weather(location)

    return ApiResponse.success(
        data=_weather_result_to_dict(result),
        message="天气查询成功",
    )


@router.get(
    "/location",
    summary="根据经纬度获取天气",
    description="根据 GPS 经纬度获取实时天气、预报和农业建议",
)
async def get_weather_by_location(
    lat: float = Query(..., description="纬度", ge=-90, le=90),
    lon: float = Query(..., description="经度", ge=-180, le=180),
):
    logger.info(f"[weather-api] 根据坐标查询天气: lat={lat}, lon={lon}")
    service = get_weather_service()
    result = await service.get_weather_by_coordinates(lat, lon)

    return ApiResponse.success(
        data=_weather_result_to_dict(result),
        message="定位天气查询成功",
    )


@router.get(
    "/config",
    summary="获取天气页定位配置",
    description="返回前端定位功能所需的配置项",
)
async def get_weather_config():
    return ApiResponse.success(
        data={
            "location_enabled": settings.weather_location_enabled,
            "default_city": settings.weather_default_city,
            "timeout_ms": settings.weather_location_timeout_ms,
            "high_accuracy": settings.weather_location_high_accuracy,
        },
        message="获取配置成功",
    )
