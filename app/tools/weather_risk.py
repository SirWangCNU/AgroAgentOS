"""极端天气风险分析引擎.

根据天气预报数据，自动检测霜冻、暴雨、高温、干旱等极端天气风险，
生成对应的农事应对建议。

阈值参考:
  - 霜冻: 最低温 ≤ 2℃ (≤0℃ 高, 0-2℃ 中)
  - 暴雨: 日降水 ≥ 50mm (≥100mm 高, 50-100mm 中)
  - 高温: 最高温 ≥ 35℃ (统一中)
  - 干旱: 连续 7 天降水 < 1mm (统一中)
"""

from __future__ import annotations

from typing import List, Optional

from app.schemas.weather import DailyForecastDetail, WeatherAlert


def analyze_weather_risks(
    forecast: List[DailyForecastDetail],
    crop: Optional[str] = None,
) -> List[WeatherAlert]:
    """根据预报数据计算极端天气预警.

    Args:
        forecast: 未来 N 天预报列表
        crop: 当前种植作物 (可选, 用于生成更精准的建议)

    Returns:
        预警列表, 按日期排序
    """
    alerts: List[WeatherAlert] = []

    for day in forecast:
        # 霜冻检测
        if day.min_temp <= 2:
            severity = "高" if day.min_temp <= 0 else "中"
            advice = _get_frost_advice(crop)
            alerts.append(WeatherAlert(
                alert_type="霜冻",
                date=day.date,
                severity=severity,
                advice=advice,
            ))

        # 暴雨检测
        if day.precipitation_mm >= 50:
            severity = "高" if day.precipitation_mm >= 100 else "中"
            advice = _get_rainstorm_advice(crop)
            alerts.append(WeatherAlert(
                alert_type="暴雨",
                date=day.date,
                severity=severity,
                advice=advice,
            ))

        # 高温检测
        if day.max_temp >= 35:
            advice = _get_heat_advice(crop)
            alerts.append(WeatherAlert(
                alert_type="高温",
                date=day.date,
                severity="中",
                advice=advice,
            ))

    # 干旱检测: 连续 7 天降水 < 1mm
    if len(forecast) >= 7:
        total_precip = sum(d.precipitation_mm for d in forecast[:7])
        if total_precip < 1:
            advice = _get_drought_advice(crop)
            alerts.append(WeatherAlert(
                alert_type="干旱",
                date=forecast[0].date,
                severity="中",
                advice=advice,
            ))

    return alerts


# ============================================================
# 各类预警的农事建议生成
# ============================================================

def _get_frost_advice(crop: Optional[str] = None) -> str:
    """生成霜冻应对建议."""
    base = "夜间注意覆盖或熏烟防霜，敏感作物提前转移至室内"
    if crop:
        crop_lower = crop.lower()
        if any(k in crop_lower for k in ["番茄", "辣椒", "黄瓜", "西瓜", "甜瓜"]):
            return f"{crop}为喜温作物，霜冻风险极高，建议提前覆盖地膜或移入大棚"
        if any(k in crop_lower for k in ["小麦", "大麦"]):
            return f"{crop}有一定耐寒性，但极端霜冻仍需关注，可适当灌水防冻"
    return base


def _get_rainstorm_advice(crop: Optional[str] = None) -> str:
    """生成暴雨应对建议."""
    base = "检查排水沟渠，低洼地块提前排水，大棚加固"
    if crop:
        crop_lower = crop.lower()
        if any(k in crop_lower for k in ["水稻"]):
            return f"暴雨后注意{crop}田间水位管理，及时排水防涝，预防稻瘟病"
        if any(k in crop_lower for k in ["蔬菜", "番茄", "辣椒", "黄瓜"]):
            return f"暴雨对{crop}影响大，建议加固支架，雨后及时喷施杀菌剂预防病害"
    return base


def _get_heat_advice(crop: Optional[str] = None) -> str:
    """生成高温应对建议."""
    base = "增加灌溉频次，叶面喷水降温，避免午间作业"
    if crop:
        crop_lower = crop.lower()
        if any(k in crop_lower for k in ["番茄", "辣椒", "西瓜"]):
            return f"高温影响{crop}坐果，建议早晚灌溉，覆盖遮阳网降温"
        if any(k in crop_lower for k in ["水稻"]):
            return f"高温热害影响{crop}抽穗扬花，建议灌深水降温"
    return base


def _get_drought_advice(crop: Optional[str] = None) -> str:
    """生成干旱应对建议."""
    base = "未来一周基本无雨，提前规划灌溉"
    if crop:
        return f"持续干旱对{crop}生长不利，建议适时补水灌溉，覆盖保墒"
    return base
