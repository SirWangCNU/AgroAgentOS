"""天气服务 - 提供天气查询、缓存和农业建议.

支持:
  - 和风天气 API (国内推荐, 免费额度)
  - OpenWeatherMap API (国际)
  - Mock 数据兜底 (无 API Key 时)

设计:
  - 异步 HTTP 调用 (httpx)
  - 内存缓存 + TTL (避免频繁调用)
  - 农业建议规则引擎
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import httpx
from loguru import logger


# ============================================================
# 数据模型
# ============================================================

@dataclass
class WeatherData:
    """当前天气数据."""
    location: str
    temperature: float
    humidity: int
    wind_speed: float
    wind_level: int
    condition: str
    rain_probability: int
    feels_like: float = 0.0
    pressure: int = 0
    visibility: float = 0.0
    uv_index: int = 0
    update_time: str = ""


@dataclass
class ForecastDay:
    """单日预报."""
    date: str
    temp_high: float
    temp_low: float
    condition: str
    condition_day: str = ""
    condition_night: str = ""
    rain_probability: int = 0
    wind_level: int = 0


@dataclass
class WeatherResult:
    """完整天气结果."""
    current: WeatherData
    forecast: List[ForecastDay] = field(default_factory=list)
    agriculture_advice: str = ""
    source: str = "mock"


# ============================================================
# 农业建议规则引擎
# ============================================================

def generate_agriculture_advice(weather: WeatherData, forecast: List[ForecastDay] | None = None) -> str:
    """根据天气条件生成农业建议."""
    advice: List[str] = []

    # 喷药建议
    if weather.rain_probability > 70:
        advice.append("降雨概率较高，不建议喷药作业，雨水会冲刷药剂")
    elif weather.wind_level > 4:
        advice.append("风速较大（>4级），不建议喷药作业，药液会飘移造成浪费和污染")
    elif weather.temperature > 35:
        advice.append("温度过高（>35℃），不建议喷药作业，易产生药害且蒸发快")
    elif 15 <= weather.temperature <= 30 and weather.wind_level <= 3 and weather.rain_probability < 30:
        advice.append("天气条件适合喷药作业，建议选择上午10点前或下午4点后")

    # 播种建议
    if weather.condition in ("大雨", "暴雨", "雷阵雨"):
        advice.append("强降雨天气，不建议播种，土壤过湿影响出苗率")
    elif weather.temperature < 10:
        advice.append("温度偏低（<10℃），需根据作物耐寒性判断是否播种")
    elif weather.temperature > 38:
        advice.append("温度过高（>38℃），不建议播种，种子易失活")

    # 灌溉建议
    if weather.rain_probability > 60:
        advice.append("未来有降雨预期，可适当减少灌溉，节约水资源")
    elif weather.temperature > 33 and weather.humidity < 40:
        advice.append("高温干燥天气，建议增加灌溉频次，避免作物萎蔫")
    elif weather.humidity > 85:
        advice.append("空气湿度较大，注意排水防涝，避免根系缺氧")

    # 采收建议
    if weather.condition in ("小雨", "中雨", "阴"):
        advice.append("阴雨天气，建议抢晴采收，避免果实腐烂和品质下降")
    elif weather.temperature > 35:
        advice.append("高温天气，建议早晚采收，避免日灼伤害和品质下降")

    # 预警
    if forecast:
        tomorrow = forecast[0] if len(forecast) > 0 else None
        if tomorrow and tomorrow.rain_probability > 60:
            advice.append(f"明日预报有雨（概率{tomorrow.rain_probability}%），注意提前做好防雨准备")
        if tomorrow and tomorrow.temp_high > 37:
            advice.append(f"明日高温预报（{tomorrow.temp_high}℃），注意遮阳防晒和灌溉降温")

    return "；".join(advice) if advice else "天气条件正常，可正常进行农事活动"


# ============================================================
# Mock 数据
# ============================================================

MOCK_CITIES: Dict[str, Dict[str, Any]] = {
    "北京": {"temp": 28, "humidity": 65, "wind_speed": 3.2, "wind_level": 3, "condition": "多云", "rain": 20},
    "上海": {"temp": 30, "humidity": 75, "wind_speed": 4.0, "wind_level": 3, "condition": "阴", "rain": 45},
    "广州": {"temp": 33, "humidity": 80, "wind_speed": 2.5, "wind_level": 2, "condition": "小雨", "rain": 70},
    "成都": {"temp": 26, "humidity": 70, "wind_speed": 1.8, "wind_level": 2, "condition": "多云", "rain": 30},
    "武汉": {"temp": 31, "humidity": 68, "wind_speed": 2.8, "wind_level": 2, "condition": "晴", "rain": 10},
    "西安": {"temp": 29, "humidity": 55, "wind_speed": 2.0, "wind_level": 2, "condition": "晴", "rain": 5},
    "南京": {"temp": 30, "humidity": 72, "wind_speed": 3.0, "wind_level": 2, "condition": "多云", "rain": 35},
    "杭州": {"temp": 29, "humidity": 78, "wind_speed": 2.5, "wind_level": 2, "condition": "阴", "rain": 50},
    "郑州": {"temp": 32, "humidity": 58, "wind_speed": 3.5, "wind_level": 3, "condition": "晴", "rain": 10},
    "长沙": {"temp": 31, "humidity": 75, "wind_speed": 2.2, "wind_level": 2, "condition": "多云", "rain": 40},
}

MOCK_FORECAST: List[Dict[str, Any]] = [
    {"date": "明天", "temp_high": 30, "temp_low": 22, "condition": "多云", "rain": 25, "wind_level": 3},
    {"date": "后天", "temp_high": 28, "temp_low": 20, "condition": "小雨", "rain": 60, "wind_level": 2},
    {"date": "大后天", "temp_high": 27, "temp_low": 19, "condition": "阴", "rain": 40, "wind_level": 2},
]


def _build_mock_result(location: str) -> WeatherResult:
    """构建 Mock 天气结果."""
    data = MOCK_CITIES.get(location, MOCK_CITIES["北京"])
    current = WeatherData(
        location=location,
        temperature=data["temp"],
        humidity=data["humidity"],
        wind_speed=data["wind_speed"],
        wind_level=data["wind_level"],
        condition=data["condition"],
        rain_probability=data["rain"],
        feels_like=data["temp"] + 2,
        pressure=1013,
        visibility=10.0,
        uv_index=5,
        update_time="模拟数据",
    )
    forecast = [
        ForecastDay(
            date=d["date"],
            temp_high=d["temp_high"],
            temp_low=d["temp_low"],
            condition=d["condition"],
            rain_probability=d["rain"],
            wind_level=d["wind_level"],
        )
        for d in MOCK_FORECAST
    ]
    advice = generate_agriculture_advice(current, forecast)
    return WeatherResult(current=current, forecast=forecast, agriculture_advice=advice, source="mock")


# ============================================================
# 缓存
# ============================================================

class _WeatherCache:
    """简单的内存缓存."""

    def __init__(self, ttl_seconds: int = 1800):
        self._ttl = ttl_seconds
        self._store: Dict[str, tuple[float, WeatherResult]] = {}
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Optional[WeatherResult]:
        async with self._lock:
            entry = self._store.get(key)
            if entry and (time.time() - entry[0]) < self._ttl:
                return entry[1]
            return None

    async def set(self, key: str, value: WeatherResult) -> None:
        async with self._lock:
            self._store[key] = (time.time(), value)

    def clear(self) -> None:
        self._store.clear()


_cache = _WeatherCache(ttl_seconds=1800)


# ============================================================
# 和风天气 API
# ============================================================

class QWeatherClient:
    """和风天气 API 客户端 (免费版)."""

    BASE_URL = "https://devapi.qweather.com/v7"
    GEO_URL = "https://geoapi.qweather.com/v2"

    def __init__(self, api_key: str):
        self._api_key = api_key
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=10.0)
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def _get_location_id(self, city: str) -> Optional[str]:
        """通过城市名获取 location ID."""
        client = await self._get_client()
        try:
            resp = await client.get(
                f"{self.GEO_URL}/city/lookup",
                params={"location": city, "key": self._api_key, "lang": "zh"},
            )
            data = resp.json()
            if data.get("code") == "200" and data.get("location"):
                return data["location"][0]["id"]
        except Exception as e:
            logger.warning(f"[QWeather] 城市查询失败: {e}")
        return None

    async def get_now(self, location_id: str) -> Optional[Dict[str, Any]]:
        """获取实时天气."""
        client = await self._get_client()
        try:
            resp = await client.get(
                f"{self.BASE_URL}/weather/now",
                params={"location": location_id, "key": self._api_key, "lang": "zh"},
            )
            data = resp.json()
            if data.get("code") == "200":
                return data.get("now")
        except Exception as e:
            logger.warning(f"[QWeather] 实时天气查询失败: {e}")
        return None

    async def get_forecast(self, location_id: str, days: int = 3) -> List[Dict[str, Any]]:
        """获取天气预报."""
        client = await self._get_client()
        try:
            resp = await client.get(
                f"{self.BASE_URL}/weather/3d",
                params={"location": location_id, "key": self._api_key, "lang": "zh"},
            )
            data = resp.json()
            if data.get("code") == "200":
                return data.get("daily", [])[:days]
        except Exception as e:
            logger.warning(f"[QWeather] 天气预报查询失败: {e}")
        return []


# ============================================================
# 天气服务主类
# ============================================================

class WeatherService:
    """天气服务 - 统一入口."""

    def __init__(self, api_key: str = "", provider: str = "auto"):
        self._api_key = api_key
        self._provider = provider
        self._qweather: Optional[QWeatherClient] = None

        if api_key and provider in ("auto", "qweather"):
            self._qweather = QWeatherClient(api_key)
            logger.info("[WeatherService] 使用和风天气 API")
        else:
            logger.info("[WeatherService] 未配置天气 API Key, 使用 Mock 数据")

    async def close(self) -> None:
        if self._qweather:
            await self._qweather.close()

    async def get_weather(self, location: str) -> WeatherResult:
        """获取天气 (带缓存)."""
        cache_key = location.strip()
        cached = await _cache.get(cache_key)
        if cached:
            logger.debug(f"[WeatherService] 缓存命中: {location}")
            return cached

        result = await self._fetch_weather(location)
        await _cache.set(cache_key, result)
        return result

    async def _fetch_weather(self, location: str) -> WeatherResult:
        """从 API 或 Mock 获取天气."""
        if self._qweather:
            try:
                return await self._fetch_qweather(location)
            except Exception as e:
                logger.warning(f"[WeatherService] 和风天气 API 调用失败, 回退 Mock: {e}")

        return _build_mock_result(location)

    async def _fetch_qweather(self, location: str) -> WeatherResult:
        """从和风天气 API 获取数据."""
        location_id = await self._qweather._get_location_id(location)
        if not location_id:
            logger.warning(f"[QWeather] 未找到城市: {location}, 回退 Mock")
            return _build_mock_result(location)

        now_data, forecast_data = await asyncio.gather(
            self._qweather.get_now(location_id),
            self._qweather.get_forecast(location_id, 3),
        )

        if not now_data:
            return _build_mock_result(location)

        current = WeatherData(
            location=location,
            temperature=float(now_data.get("temp", 25)),
            humidity=int(now_data.get("humidity", 60)),
            wind_speed=float(now_data.get("windSpeed", 2.0)),
            wind_level=int(now_data.get("windScale", 2)),
            condition=now_data.get("text", "多云"),
            rain_probability=0,
            feels_like=float(now_data.get("feelsLike", 25)),
            pressure=int(now_data.get("pressure", 1013)),
            visibility=float(now_data.get("vis", 10.0)),
            update_time=now_data.get("obsTime", ""),
        )

        forecast = []
        for day in forecast_data:
            forecast.append(ForecastDay(
                date=day.get("fxDate", ""),
                temp_high=float(day.get("tempMax", 30)),
                temp_low=float(day.get("tempMin", 20)),
                condition=day.get("textDay", "多云"),
                condition_day=day.get("textDay", ""),
                condition_night=day.get("textNight", ""),
                rain_probability=int(day.get("precip", 0)),
                wind_level=int(day.get("windScaleDay", 2)),
            ))

        advice = generate_agriculture_advice(current, forecast)
        return WeatherResult(current=current, forecast=forecast, agriculture_advice=advice, source="qweather")


# ============================================================
# 全局单例
# ============================================================

_weather_service: Optional[WeatherService] = None


def get_weather_service() -> WeatherService:
    """获取天气服务单例."""
    global _weather_service
    if _weather_service is None:
        from app.config import settings
        # 从环境变量读取天气 API Key (可选)
        import os
        api_key = os.environ.get("QWEATHER_API_KEY", "")
        _weather_service = WeatherService(api_key=api_key)
    return _weather_service


def reset_weather_service() -> None:
    """重置天气服务 (测试用)."""
    global _weather_service
    if _weather_service:
        asyncio.get_event_loop().create_task(_weather_service.close())
    _weather_service = None
