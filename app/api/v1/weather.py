"""天气 API 端点 - 供前端调用.

GET /api/v1/weather?location=北京   - 获取天气数据
"""

from __future__ import annotations

from fastapi import APIRouter, Query
from loguru import logger

from app.schemas.common import ApiResponse
from app.services.weather_service import get_weather_service

router = APIRouter(prefix="/weather", tags=["weather"])


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
        data={
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
        },
        message="天气查询成功",
    )
