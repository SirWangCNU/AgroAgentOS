"""天气查询工具 - 提供实时天气和农业建议.

当前为占位实现，使用模拟数据。
正式环境需要接入天气API（和风天气、OpenWeatherMap等）。
"""

from __future__ import annotations

from typing import Dict, Optional
from dataclasses import dataclass

from langchain_core.tools import tool
from loguru import logger


@dataclass
class WeatherData:
    """天气数据结构."""
    location: str
    temperature: float  # 温度(℃)
    humidity: int       # 湿度(%)
    wind_speed: float   # 风速(m/s)
    wind_level: int     # 风级
    condition: str      # 天气状况
    rain_probability: int  # 降雨概率(%)
    forecast: list       # 预报


def get_agriculture_advice(weather: WeatherData) -> str:
    """根据天气条件生成农业建议."""
    advice = []

    # 喷药建议
    if weather.rain_probability > 70:
        advice.append("降雨概率较高，不建议喷药作业，雨水会冲刷药剂")
    elif weather.wind_level > 4:
        advice.append("风速较大，不建议喷药作业，药液会飘移")
    elif weather.temperature > 35:
        advice.append("温度过高，不建议喷药作业，易产生药害")
    else:
        advice.append("天气条件适合喷药作业")

    # 播种建议
    if weather.condition in ["大雨", "暴雨"]:
        advice.append("强降雨天气，不建议播种，土壤过湿影响出苗")
    elif weather.temperature < 10:
        advice.append("温度偏低，需根据作物耐寒性判断是否播种")

    # 灌溉建议
    if weather.rain_probability > 60:
        advice.append("未来有降雨，可适当减少灌溉")
    elif weather.temperature > 33 and weather.humidity < 40:
        advice.append("高温干燥，建议增加灌溉频次")

    # 采收建议
    if weather.condition in ["小雨", "中雨", "阴"]:
        advice.append("阴雨天气，建议抢晴采收，避免果实腐烂")
    elif weather.temperature > 35:
        advice.append("高温天气，建议早晚采收，避免日灼伤害")

    return "；".join(advice) if advice else "天气条件正常，可正常进行农事活动"


def get_weather_icon(condition: str) -> str:
    """获取天气图标."""
    icons = {
        "晴": "fa-sun",
        "多云": "fa-cloud-sun",
        "阴": "fa-cloud",
        "小雨": "fa-cloud-rain",
        "中雨": "fa-cloud-showers-heavy",
        "大雨": "fa-cloud-showers-heavy",
        "暴雨": "fa-poo-storm",
        "雷阵雨": "fa-bolt",
        "雪": "fa-snowflake",
        "雾": "fa-smog",
    }
    return icons.get(condition, "fa-cloud")


# ============ 模拟数据（开发/演示用） ============

MOCK_WEATHER_DATA: Dict[str, Dict] = {
    "北京": {
        "location": "北京",
        "temperature": 28,
        "humidity": 65,
        "wind_speed": 3.2,
        "wind_level": 3,
        "condition": "多云",
        "rain_probability": 20,
    },
    "上海": {
        "location": "上海",
        "temperature": 30,
        "humidity": 75,
        "wind_speed": 4.0,
        "wind_level": 3,
        "condition": "阴",
        "rain_probability": 45,
    },
    "广州": {
        "location": "广州",
        "temperature": 33,
        "humidity": 80,
        "wind_speed": 2.5,
        "wind_level": 2,
        "condition": "小雨",
        "rain_probability": 70,
    },
    "成都": {
        "location": "成都",
        "temperature": 26,
        "humidity": 70,
        "wind_speed": 1.8,
        "wind_level": 2,
        "condition": "多云",
        "rain_probability": 30,
    },
    "武汉": {
        "location": "武汉",
        "temperature": 31,
        "humidity": 68,
        "wind_speed": 2.8,
        "wind_level": 2,
        "condition": "晴",
        "rain_probability": 10,
    },
}

MOCK_FORECAST = [
    {"date": "明天", "temp_high": 30, "temp_low": 22, "condition": "多云", "rain_probability": 25},
    {"date": "后天", "temp_high": 28, "temp_low": 20, "condition": "小雨", "rain_probability": 60},
    {"date": "大后天", "temp_high": 27, "temp_low": 19, "condition": "阴", "rain_probability": 40},
]


@tool
def get_weather(location: str) -> str:
    """获取指定位置的实时天气和农业建议。

    Args:
        location: 地点名称，如"北京"、"上海"、"广州"等

    Returns:
        天气信息和农业建议（Markdown格式）
    """
    logger.info(f"[weather_tool] 查询天气: {location}")

    # 模拟数据查询（正式环境替换为API调用）
    data = MOCK_WEATHER_DATA.get(location)
    if not data:
        # 默认返回通用天气
        data = {
            "location": location,
            "temperature": 25,
            "humidity": 60,
            "wind_speed": 2.5,
            "wind_level": 2,
            "condition": "多云",
            "rain_probability": 30,
        }

    weather = WeatherData(
        location=data["location"],
        temperature=data["temperature"],
        humidity=data["humidity"],
        wind_speed=data["wind_speed"],
        wind_level=data["wind_level"],
        condition=data["condition"],
        rain_probability=data["rain_probability"],
        forecast=MOCK_FORECAST,
    )

    # 生成农业建议
    agri_advice = get_agriculture_advice(weather)
    icon = get_weather_icon(weather.condition)

    # 构建Markdown输出
    lines = [
        f"## {weather.location} 实时天气",
        "",
        f"| 指标 | 数值 |",
        f"|------|------|",
        f"| 天气状况 | {weather.condition} |",
        f"| 温度 | {weather.temperature}℃ |",
        f"| 湿度 | {weather.humidity}% |",
        f"| 风速 | {weather.wind_speed}m/s（{weather.wind_level}级） |",
        f"| 降雨概率 | {weather.rain_probability}% |",
        "",
        "## 未来三天预报",
        "",
        "| 日期 | 天气 | 温度 | 降雨概率 |",
        "|------|------|------|----------|",
    ]

    for day in weather.forecast:
        lines.append(
            f"| {day['date']} | {day['condition']} | {day['temp_low']}~{day['temp_high']}℃ | {day['rain_probability']}% |"
        )

    lines.extend([
        "",
        "## 农业建议",
        "",
        agri_advice,
        "",
        "---",
        "*数据来源：天气服务（开发环境使用模拟数据）*",
    ])

    return "\n".join(lines)
