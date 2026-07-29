"""用户查询中的农场意图识别。"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class QueryIntent:
    """查询关联的用户农场数据范围。"""

    has_farm: bool = False
    farm_keywords: list[str] = field(default_factory=list)


_FARM_KEYWORDS = [
    "农场", "地块", "田块", "种植", "土壤", "作物", "生长", "播种", "收获",
    "施肥", "灌溉", "大棚", "温室", "小麦", "玉米", "水稻", "番茄", "黄瓜",
    "草莓", "生长期", "播种期", "分蘖期", "开花期", "结果期", "休耕", "壤土",
    "黏土", "沙土", "有机质", "面积", "亩", "耕地",
]


def detect_intent(query: str) -> QueryIntent:
    """识别农场关键词；未命中时仍注入简要农场概况。"""
    farm_hits = [keyword for keyword in _FARM_KEYWORDS if keyword in query]
    return QueryIntent(has_farm=True, farm_keywords=farm_hits)
