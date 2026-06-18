"""农业日历工具 - 节气提醒与种植历生成.

提供两大功能:
  1. solar_term_reminder: 根据日期返回当前节气及农事提醒
  2. generate_planting_calendar: 根据作物和地理位置生成全年种植历

依赖:
  - cnlunar: 农历/节气计算库
  - data/solar_terms.json: 节气提醒数据
  - data/crop_calendar_templates.json: 作物种植历模板
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from langchain_core.tools import tool
from loguru import logger


# ============================================================
# 数据加载
# ============================================================

_DATA_DIR = Path(__file__).parent.parent.parent / "data"


def _load_json(filename: str) -> Dict[str, Any]:
    """加载 JSON 数据文件."""
    filepath = _DATA_DIR / filename
    if not filepath.exists():
        logger.warning(f"[calendar_tools] 数据文件不存在: {filepath}")
        return {}
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


# ============================================================
# 节气计算
# ============================================================

def _get_solar_term(date: datetime) -> Optional[str]:
    """使用 cnlunar 计算指定日期的节气.

    如果 cnlunar 不可用, 使用简化算法 (基于日期范围近似).
    """
    try:
        import cnlunar
        lunar = cnlunar.Lunar(date, godType="8char")
        term = lunar.term
        if term and term.strip():
            return term.strip()
    except ImportError:
        logger.warning("[calendar_tools] cnlunar 未安装, 使用日期近似算法")
    except Exception as e:
        logger.warning(f"[calendar_tools] cnlunar 计算失败: {e}, 使用日期近似算法")

    # 简化算法: 基于日期范围近似
    return _approximate_solar_term(date)


def _approximate_solar_term(date: datetime) -> Optional[str]:
    """基于日期范围的节气近似算法 (兜底方案)."""
    month_day = date.month * 100 + date.day

    term_ranges = [
        (105, 106, "小寒"), (120, 121, "大寒"),
        (203, 205, "立春"), (218, 220, "雨水"),
        (305, 307, "惊蛰"), (320, 322, "春分"),
        (404, 406, "清明"), (419, 421, "谷雨"),
        (505, 507, "立夏"), (520, 522, "小满"),
        (605, 607, "芒种"), (621, 622, "夏至"),
        (706, 708, "小暑"), (722, 724, "大暑"),
        (807, 809, "立秋"), (822, 824, "处暑"),
        (907, 909, "白露"), (922, 924, "秋分"),
        (1008, 1009, "寒露"), (1023, 1024, "霜降"),
        (1107, 1108, "立冬"), (1122, 1123, "小雪"),
        (1206, 1208, "大雪"), (1221, 1223, "冬至"),
    ]

    for start, end, term in term_ranges:
        if start <= month_day <= end:
            return term

    # 找最近的节气
    min_dist = float("inf")
    nearest = None
    for start, end, term in term_ranges:
        mid = (start + end) / 2
        dist = abs(month_day - mid)
        if dist < min_dist:
            min_dist = dist
            nearest = term
    return nearest


# ============================================================
# 节气提醒工具
# ============================================================

@tool
def solar_term_reminder(date: str = "", crop: str = "") -> str:
    """返回指定日期对应的节气及相关农事提醒。

    当用户询问"现在是什么节气"、"清明前后要注意什么"、"节气农事"等问题时使用。
    可根据作物过滤相关提醒。

    Args:
        date: 日期字符串 YYYY-MM-DD，默认今天
        crop: 作物名称，可选，如"水稻"、"玉米"，用于过滤相关提醒

    Returns:
        节气信息和农事提醒（Markdown格式）
    """
    logger.info(f"[calendar_tools] 节气查询: date={date}, crop={crop}")

    # 解析日期
    if date:
        try:
            target_date = datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            target_date = datetime.now()
    else:
        target_date = datetime.now()

    # 计算节气
    term = _get_solar_term(target_date)
    if not term:
        return "无法确定当前节气，请稍后重试"

    # 加载提醒数据
    solar_terms_data = _load_json("solar_terms.json")
    term_info = solar_terms_data.get(term, {})

    if not term_info:
        return f"当前节气: **{term}**\n\n暂无该节气的详细农事提醒数据。"

    # 构建输出
    lines = [
        f"## 🌾 节气: {term}",
        "",
        f"**日期范围**: {term_info.get('date_range', '未知')}",
        "",
    ]

    # 通用提醒
    general = term_info.get("general", [])
    if general:
        lines.append("### 通用农事提醒")
        lines.append("")
        for item in general:
            lines.append(f"- {item}")
        lines.append("")

    # 作物特定提醒
    crops_data = term_info.get("crops", {})
    if crop:
        # 过滤特定作物
        crop_reminders = []
        for crop_name, reminders in crops_data.items():
            if crop.lower() in crop_name.lower() or crop_name.lower() in crop.lower():
                crop_reminders.extend(reminders)

        if crop_reminders:
            lines.append(f"### {crop}种植提醒")
            lines.append("")
            for item in crop_reminders:
                lines.append(f"- {item}")
            lines.append("")
        else:
            lines.append(f"### {crop}种植提醒")
            lines.append("")
            lines.append(f"暂无{crop}在{term}节气的专项提醒。")
            lines.append("")
    elif crops_data:
        lines.append("### 作物专项提醒")
        lines.append("")
        for crop_name, reminders in crops_data.items():
            lines.append(f"**{crop_name}**:")
            for item in reminders:
                lines.append(f"  - {item}")
        lines.append("")

    return "\n".join(lines)


# ============================================================
# 气候分区
# ============================================================

def _determine_climate_zone(latitude: float) -> str:
    """根据纬度判断气候分区.

    分区方案:
      - 华南: < 25°N (广东、广西、海南、福建南部)
      - 华中: 25°N - 35°N (长江流域、华东大部)
      - 华北: 35°N - 42°N (京津冀、山东、河南北部)
      - 东北: ≥ 42°N (黑龙江、吉林、内蒙古北部)
    """
    if latitude < 25:
        return "华南"
    elif latitude < 35:
        return "华中"
    elif latitude < 42:
        return "华北"
    else:
        return "东北"


# ============================================================
# 种植历生成工具
# ============================================================

CATEGORY_ICONS = {
    "播种": "🌱",
    "施肥": "💛",
    "防虫": "🛡️",
    "管理": "🔧",
    "收获": "🌾",
}


@tool
def generate_planting_calendar(crop: str, latitude: float, longitude: float) -> str:
    """根据作物种类和地理位置生成全年种植历。

    当用户询问"全年怎么安排"、"种植计划"、"什么时候播种"等问题时使用。
    返回按时间顺序排列的各阶段农事要点。

    Args:
        crop: 作物名称，如"水稻"、"玉米"、"冬小麦"、"番茄"
        latitude: 纬度，如北京39.9、上海31.2、广州23.1
        longitude: 经度，如北京116.4、上海121.5、广州113.3

    Returns:
        全年种植历（Markdown格式）
    """
    logger.info(f"[calendar_tools] 种植历查询: crop={crop}, lat={latitude}, lon={longitude}")

    # 加载模板数据
    templates = _load_json("crop_calendar_templates.json")

    # 查找作物模板 (支持模糊匹配)
    template = None
    matched_crop = crop
    for crop_name, tmpl in templates.items():
        if crop.lower() in crop_name.lower() or crop_name.lower() in crop.lower():
            template = tmpl
            matched_crop = crop_name
            break

    if not template:
        available = ", ".join(templates.keys())
        return f"暂未收录「{crop}」的种植历模板。\n\n当前支持的作物: {available}"

    # 判断气候分区
    zone = _determine_climate_zone(latitude)
    zone_config = template["zones"].get(zone)

    if not zone_config:
        available_zones = ", ".join(template["zones"].keys())
        return (
            f"「{matched_crop}」暂不支持{zone}地区种植。\n"
            f"当前支持的区域: {available_zones}"
        )

    # 计算播种起始日期
    sowing_window = zone_config["sowing_window"]
    sowing_start_str = sowing_window.split("~")[0]
    current_year = datetime.now().year

    try:
        # 处理跨年作物 (如冬小麦 10月播种)
        month_day = [int(x) for x in sowing_start_str.split("-")]
        if month_day[0] >= 9:
            sowing_start = datetime(current_year, month_day[0], month_day[1])
        else:
            sowing_start = datetime(current_year, month_day[0], month_day[1])
    except (ValueError, IndexError):
        sowing_start = datetime.now()

    # 生成各阶段
    stages = template["stage_offsets_days"]
    lines = [
        f"## 📅 {matched_crop}全年种植历",
        "",
        f"**气候分区**: {zone} | **播种窗口**: {sowing_window}",
        f"**年播种季数**: {zone_config.get('seasons', 1)}季",
        "",
        "---",
        "",
    ]

    for stage in stages:
        stage_date = sowing_start + timedelta(days=stage["offset"])
        icon = CATEGORY_ICONS.get(stage["category"], "📌")

        lines.append(f"### {icon} {stage['name']}")
        lines.append(f"- **日期**: {stage_date.strftime('%m月%d日')}")
        lines.append(f"- **类别**: {stage['category']}")
        lines.append(f"- **要点**: {stage['note']}")
        lines.append("")

    # 结尾提示
    lines.append("---")
    lines.append("")
    lines.append("💡 **提示**: 以上为参考时间，实际农事安排请结合当地气候、土壤条件和作物品种特性调整。")

    return "\n".join(lines)
