"""市场行情 LangChain 工具 - 供 Agent 调用.

工具列表:
  - get_market_price: 查询农产品批发市场价格
  - get_supply_demand: 查询农产品供需数据
  - get_policy_subsidies: 按位置查询农业政策补贴
  - get_market_analysis: LLM 综合分析 (价格预测 + 销售建议)

设计:
  - @tool 装饰器自动注册
  - 内部委托给 MarketService (单例)
  - 异步执行, 失败返回错误字符串不抛异常
"""

from __future__ import annotations

import asyncio

from langchain_core.tools import tool
from loguru import logger

from app.services.market_service import get_market_service


def _run_async(coro):
    """在同步工具中运行异步代码 (仿 weather_tool 模式)."""
    try:
        loop = asyncio.get_running_loop()
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            return pool.submit(asyncio.run, coro).result()
    except RuntimeError:
        return asyncio.run(coro)


@tool
def get_market_price(crop: str, location: str = "北京") -> str:
    """查询农产品批发市场价格.

    当用户询问某农产品的当前价格、价格走势、涨价降价时使用。
    返回主要批发市场的报价、均价和趋势。

    Args:
        crop: 农产品名称, 如 "水稻"、"小麦"、"玉米"、"苹果"、"番茄"
        location: 市场所在城市, 默认 "北京"

    Returns:
        市场价格信息 (Markdown 格式)
    """
    service = get_market_service()
    result = _run_async(service.get_market_price(crop, location))

    lines = [f"### {crop} 市场价格 ({location})"]
    lines.append(f"- 均价: **{result.average_price} 元/公斤**")
    lines.append(f"- 趋势: {_trend_zh(result.trend)}")
    lines.append(f"- 数据来源: {result.source}")
    lines.append(f"- 更新时间: {result.update_time}")
    lines.append("")
    lines.append("| 市场 | 价格 (元/公斤) | 涨跌 | 涨跌幅 | 日期 |")
    lines.append("|------|----------------|------|--------|------|")
    for item in result.items:
        change_str = f"{item.change:+.2f}" if item.change != 0 else "0.00"
        lines.append(
            f"| {item.market} | {item.price:.2f} | {change_str} | "
            f"{item.change_percent:+.2f}% | {item.date} |"
        )
    return "\n".join(lines)


@tool
def get_supply_demand(crop: str) -> str:
    """查询农产品供需分析数据。

    当用户询问某农产品的产量、库存、进出口、供需平衡时使用。
    返回供需数据和文字分析。

    Args:
        crop: 农产品名称, 如 "水稻"、"小麦"、"玉米"

    Returns:
        供需分析数据 (Markdown 格式)
    """
    service = get_market_service()
    result = _run_async(service.get_supply_demand(crop))

    lines = [f"### {crop} 供需分析"]
    lines.append(f"- 产量: {result.production} 万吨")
    lines.append(f"- 消费量: {result.consumption} 万吨")
    lines.append(f"- 进口: {result.import_volume} 万吨")
    lines.append(f"- 出口: {result.export_volume} 万吨")
    lines.append(f"- 库存: {result.stock} 万吨")
    lines.append(f"- 供需比: {result.supply_demand_ratio}")
    lines.append(f"- 分析: {result.analysis}")
    lines.append(f"- 数据来源: {result.source}")
    return "\n".join(lines)


@tool
def get_policy_subsidies(location: str = "北京") -> str:
    """按位置查询农业政策补贴信息。

    当用户询问农业补贴、惠农政策、补贴申报时使用。
    根据用户所在地区返回可申请的补贴政策。

    Args:
        location: 用户所在地区/城市, 如 "北京"、"山东"、"上海"

    Returns:
        政策补贴列表 (Markdown 格式)
    """
    service = get_market_service()
    result = _run_async(service.get_policy_subsidies(location))

    if not result.policies:
        return f"### {location} 政策补贴\n\n暂无匹配的政策补贴信息."

    lines = [f"### {location} 农业政策补贴"]
    lines.append(f"- 数据来源: {result.source}")
    lines.append(f"- 更新时间: {result.update_time}")
    lines.append("")
    for i, p in enumerate(result.policies, 1):
        lines.append(f"#### {i}. {p.title}")
        lines.append(f"- 类别: {p.category}")
        lines.append(f"- 补贴标准: {p.subsidy_amount}")
        lines.append(f"- 补贴对象: {p.target}")
        lines.append(f"- 申报条件: {p.conditions}")
        lines.append(f"- 截止日期: {p.deadline}")
        lines.append(f"- 适用地区: {p.region}")
        lines.append(f"- 来源: {p.source_url}")
        lines.append("")
    return "\n".join(lines)


@tool
def get_market_analysis(crop: str, location: str = "北京") -> str:
    """基于价格、供需、政策数据生成综合市场分析。

    当用户询问某农产品是否适合卖、什么时候卖、价格预测、销售建议时使用。
    综合价格行情、供需数据、政策补贴给出销售策略建议。

    Args:
        crop: 农产品名称, 如 "水稻"、"苹果"
        location: 用户所在地区/城市, 默认 "北京"

    Returns:
        综合分析报告 (Markdown 格式, 含价格预测和销售建议)
    """
    service = get_market_service()
    result = _run_async(service.get_market_analysis(crop, location))

    lines = [f"# {crop} 市场分析报告 ({location})"]
    lines.append("")
    lines.append("## 价格摘要")
    lines.append(result.price_summary)
    lines.append("")
    lines.append("## 走势预测")
    lines.append(result.trend_forecast)
    lines.append("")
    lines.append("## 供需摘要")
    lines.append(result.supply_demand_summary)
    lines.append("")
    lines.append("## 政策摘要")
    lines.append(result.policy_summary)
    lines.append("")
    lines.append("## 销售建议")
    lines.append(result.sales_advice)
    lines.append("")
    lines.append("## 风险提示")
    lines.append(result.risk_warning)
    lines.append("")
    lines.append(f"---\n*分析来源: {result.source}*")
    return "\n".join(lines)


def _trend_zh(trend: str) -> str:
    """趋势中文."""
    return {
        "up": "↑ 上涨",
        "down": "↓ 下跌",
        "stable": "→ 平稳",
    }.get(trend, trend)
