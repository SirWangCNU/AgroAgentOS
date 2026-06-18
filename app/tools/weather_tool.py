"""天气查询工具 - LangChain Tool 封装.

调用 WeatherService 获取天气数据和农业建议。
WeatherService 负责 API 调用、缓存和 Mock 兜底。
"""

from __future__ import annotations

import asyncio

from langchain_core.tools import tool
from loguru import logger


def _run_async(coro):
    """在同步工具中运行异步代码."""
    try:
        loop = asyncio.get_running_loop()
        # 已有事件循环，用 nest_asyncio 或直接创建新任务
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            return pool.submit(asyncio.run, coro).result()
    except RuntimeError:
        return asyncio.run(coro)


def _get_weather_icon(condition: str) -> str:
    """获取天气图标."""
    icons = {
        "晴": "☀️", "多云": "⛅", "阴": "☁️",
        "小雨": "🌧️", "中雨": "🌧️", "大雨": "⛈️",
        "暴雨": "⛈️", "雷阵雨": "⛈️", "雪": "❄️", "雾": "🌫️",
    }
    return icons.get(condition, "☁️")


@tool
def get_weather_forecast(location: str, days: int = 7) -> str:
    """获取未来N天天气预报和极端天气预警。

    当用户询问未来天气、是否会有霜冻/暴雨/高温、或需要天气预警时使用。
    返回天气预报表格和预警信息，预警会在回复开头醒目标注。

    Args:
        location: 地点名称，如"北京"、"上海"、"广州"、"成都"等
        days: 预报天数，默认7天

    Returns:
        天气预报和预警信息（Markdown格式）
    """
    logger.info(f"[weather_tool] 查询天气预报: {location}, {days}天")

    from app.services.weather_service import get_weather_service

    service = get_weather_service()
    result = _run_async(service.get_forecast_with_alerts(location, days))

    lines = []

    # 预警信息置顶显示
    if result.alerts:
        lines.append("## ⚠️ 极端天气预警")
        lines.append("")
        for alert in result.alerts:
            severity_icon = "🔴" if alert.severity == "高" else "🟡"
            lines.append(f"{severity_icon} **{alert.alert_type}** ({alert.date}) - {alert.severity}风险")
            lines.append(f"   {alert.advice}")
            lines.append("")

    # 天气预报表格
    lines.append(f"## {location} 未来{len(result.daily)}天天气预报")
    lines.append("")
    lines.append("| 日期 | 天气 | 温度 | 降水量 | 风力 |")
    lines.append("|------|------|------|--------|------|")

    for day in result.daily:
        icon = _get_weather_icon(day.condition)
        lines.append(
            f"| {day.date} | {icon} {day.condition} | "
            f"{day.min_temp}~{day.max_temp}℃ | {day.precipitation_mm}mm | {day.wind_level}级 |"
        )

    lines.append("")
    lines.append(f"---\n*数据来源: {result.source}*")

    return "\n".join(lines)


@tool
def get_weather(location: str) -> str:
    """获取指定位置的实时天气和农业建议。

    Args:
        location: 地点名称，如"北京"、"上海"、"广州"、"成都"等

    Returns:
        天气信息和农业建议（Markdown格式）
    """
    logger.info(f"[weather_tool] 查询天气: {location}")

    from app.services.weather_service import get_weather_service

    service = get_weather_service()
    result = _run_async(service.get_weather(location))

    current = result.current
    icon = _get_weather_icon(current.condition)

    lines = [
        f"## {icon} {current.location} 实时天气",
        "",
        "| 指标 | 数值 |",
        "|------|------|",
        f"| 天气状况 | {current.condition} |",
        f"| 温度 | {current.temperature}℃ (体感 {current.feels_like}℃) |",
        f"| 湿度 | {current.humidity}% |",
        f"| 风速 | {current.wind_speed}m/s（{current.wind_level}级） |",
        f"| 降雨概率 | {current.rain_probability}% |",
    ]

    if result.forecast:
        lines.extend([
            "",
            "## 未来三天预报",
            "",
            "| 日期 | 天气 | 温度 | 降雨概率 |",
            "|------|------|------|----------|",
        ])
        for day in result.forecast:
            day_icon = _get_weather_icon(day.condition)
            lines.append(
                f"| {day.date} | {day_icon} {day.condition} | "
                f"{day.temp_low}~{day.temp_high}℃ | {day.rain_probability}% |"
            )

    lines.extend([
        "",
        "## 农业建议",
        "",
        result.agriculture_advice,
        "",
        f"---\n*数据来源: {result.source}*",
    ])

    return "\n".join(lines)
