"""用户查询意图识别 (轻量关键词匹配).

根据用户问题快速判断涉及哪些业务模块, 决定注入哪些上下文数据.
不额外调用 LLM, 延迟 <1ms.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class QueryIntent:
    """查询意图分析结果."""
    has_farm: bool = False
    has_trajectory: bool = False
    farm_keywords: list[str] = field(default_factory=list)
    time_range: str = ""  # "recent" / "month" / "" (未检测到)


# ── 意图关键词 ──────────────────────────────────────────────

_FARM_KEYWORDS = [
    "农场", "地块", "田块", "种植", "土壤", "作物", "生长",
    "播种", "收获", "施肥", "灌溉", "大棚", "温室", "大棚蔬菜",
    "小麦", "玉米", "水稻", "番茄", "黄瓜", "草莓",
    "生长期", "播种期", "分蘖期", "开花期", "结果期", "休耕",
    "壤土", "黏土", "沙土", "有机质",
    "面积", "亩", "耕地",
]

_TRAJECTORY_KEYWORDS = [
    "作业", "轨迹", "深度", "耕深", "作业深度",
    "作业质量", "作业效率", "作业数据", "作业记录",
    "机械", "农机", "机手", "机具", "拖拉机",
    "旋耕", "播种机", "收割机", "喷药机",
    "幅宽", "速度", "作业面积", "行驶距离",
    "标准差", "深度均匀", "深度偏差",
    "上传", "导入", "excel",
]

# ── 时间范围关键词 ──────────────────────────────────────────

_RECENT_KEYWORDS = ["最近", "近几天", "近期", "上次", "昨天", "前天", "这周", "本周"]
_MONTH_KEYWORDS = ["这个月", "本月", "近一个月", "最近一个月"]


def detect_intent(query: str) -> QueryIntent:
    """分析用户查询, 返回意图标签.

    Args:
        query: 用户原始问题或改写后的检索 query

    Returns:
        QueryIntent 包含各模块命中情况
    """
    intent = QueryIntent()

    # 农场模块
    farm_hits = [kw for kw in _FARM_KEYWORDS if kw in query]
    if farm_hits:
        intent.has_farm = True
        intent.farm_keywords = farm_hits

    # 轨迹模块
    traj_hits = [kw for kw in _TRAJECTORY_KEYWORDS if kw in query]
    if traj_hits:
        intent.has_trajectory = True

    # 未命中特定模块时, 默认注入农场概况 (让用户数据始终可见)
    if not intent.has_farm and not intent.has_trajectory:
        intent.has_farm = True  # 默认注入农场概况

    # 时间范围
    if any(kw in query for kw in _RECENT_KEYWORDS):
        intent.time_range = "recent"
    elif any(kw in query for kw in _MONTH_KEYWORDS):
        intent.time_range = "month"

    return intent
