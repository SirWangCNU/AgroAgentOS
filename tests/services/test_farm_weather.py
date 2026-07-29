"""农场天气摘要服务测试。"""

from __future__ import annotations

import pytest

from app.models.farm import Farm
from app.models.user import User
from app.schemas.weather import FarmWeatherSummary
from app.services.weather_service import (
    DailyForecastDetail,
    WeatherData,
    WeatherForecastResult,
    WeatherResult,
    get_farm_weather_summary,
)


class FakeWeatherService:
    """隔离外部天气服务的可控替身。"""

    def __init__(self, weather: WeatherResult, forecast: WeatherForecastResult):
        self.weather = weather
        self.forecast = forecast
        self.coordinate_calls: list[tuple[float, float]] = []
        self.forecast_locations: list[str] = []

    async def get_weather_by_coordinates(self, lat: float, lon: float) -> WeatherResult:
        self.coordinate_calls.append((lat, lon))
        return self.weather

    async def get_forecast_with_alerts(self, location: str, days: int = 7) -> WeatherForecastResult:
        self.forecast_locations.append(location)
        return self.forecast


def make_weather_result(source: str) -> WeatherResult:
    return WeatherResult(
        current=WeatherData(
            location="寿光",
            temperature=28.0,
            humidity=65,
            wind_speed=3.2,
            wind_level=3,
            condition="多云",
            rain_probability=10,
            update_time="2026-07-29T10:00:00+08:00",
        ),
        agriculture_advice="不应出现在农场页面响应中",
        source=source,
    )


def make_forecast_result(source: str) -> WeatherForecastResult:
    return WeatherForecastResult(
        location="寿光",
        daily=[
            DailyForecastDetail(
                date="2026-07-30",
                min_temp=23.0,
                max_temp=36.0,
                condition="晴",
                wind_level=3,
            )
        ],
        alerts=[
            type("Alert", (), {"alert_type": "高温", "date": "2026-07-30", "severity": "中", "advice": "不应暴露"})()
        ],
        source=source,
    )


@pytest.mark.asyncio
async def test_farm_without_coordinates_returns_location_required():
    """缺失坐标时若仍请求天气服务，会错误地把默认城市天气当作农场天气。"""
    farm = Farm(name="北地", latitude=None, longitude=None)

    result = await get_farm_weather_summary(farm)

    assert result.available is False
    assert result.reason == "FARM_LOCATION_REQUIRED"
    assert result.current is None


@pytest.mark.asyncio
async def test_mock_weather_is_not_returned_as_live_data(monkeypatch: pytest.MonkeyPatch):
    """天气提供方退化为 Mock 时若仍返回数值，用户会误以为是实时天气。"""
    from app.services import weather_service

    fake = FakeWeatherService(make_weather_result("mock"), make_forecast_result("mock"))
    monkeypatch.setattr(weather_service, "get_weather_service", lambda: fake)

    result = await get_farm_weather_summary(
        Farm(name="北地", latitude=36.1, longitude=118.1)
    )

    assert result.available is False
    assert result.reason == "WEATHER_SERVICE_UNAVAILABLE"
    assert result.current is None


@pytest.mark.asyncio
async def test_live_weather_summary_returns_metrics_and_risk_without_advice(
    monkeypatch: pytest.MonkeyPatch,
):
    """摘要若带出农业建议，会违背本期只显示客观天气风险的产品边界。"""
    from app.services import weather_service

    fake = FakeWeatherService(make_weather_result("qweather"), make_forecast_result("qweather"))
    monkeypatch.setattr(weather_service, "get_weather_service", lambda: fake)

    result = await get_farm_weather_summary(
        Farm(name="北地", location="寿光", latitude=36.1, longitude=118.1)
    )

    assert result.available is True
    assert result.current.temperature == 28.0
    assert result.current.humidity == 65
    assert result.alerts[0].alert_type == "高温"
    assert result.alerts[0].severity == "中"
    assert "advice" not in result.model_dump()
    assert fake.coordinate_calls == [(36.1, 118.1)]
    assert fake.forecast_locations == ["寿光"]


@pytest.mark.asyncio
async def test_farm_weather_endpoint_uses_the_current_users_farm(
    monkeypatch: pytest.MonkeyPatch,
):
    """接口若忽略当前用户，会让任意登录用户读取其他农场的天气。"""
    from app.api.v1 import farms as farms_api

    farm = Farm(id=12, user_id=7, name="北地", latitude=36.1, longitude=118.1)
    current_user = User(id=7, username="farmer", email="farmer@example.com", hashed_password="hash")
    captured: dict[str, int] = {}

    def fake_get_farm(farm_id: int, user_id: int) -> Farm:
        captured["farm_id"] = farm_id
        captured["user_id"] = user_id
        return farm

    async def fake_summary(_: Farm) -> FarmWeatherSummary:
        return FarmWeatherSummary(available=False, reason="FARM_LOCATION_REQUIRED")

    monkeypatch.setattr(farms_api.farm_service, "get_farm", fake_get_farm)
    monkeypatch.setattr(farms_api, "get_farm_weather_summary", fake_summary)

    response = await farms_api.get_farm_weather(12, current_user)

    assert captured == {"farm_id": 12, "user_id": 7}
    assert response.code == "SUCCESS"
    assert response.data.reason == "FARM_LOCATION_REQUIRED"
