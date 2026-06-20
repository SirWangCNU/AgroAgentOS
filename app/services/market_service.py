"""市场行情服务 - 农产品价格、供需、政策补贴爬取与分析.

支持:
  - 农产品批发市场价格查询 (httpx 爬取 + Mock 兜底)
  - 供需数据分析 (产量/库存/进出口)
  - 政策补贴信息查询 (按位置, Redis 缓存 6h)
  - LLM 综合分析 (价格预测 + 销售建议)

设计:
  - 异步 HTTP 调用 (httpx)
  - 进程内 TTL 缓存 (价格/供需, 30min) + Redis 缓存 (政策, 6h)
  - Mock 数据兜底 (爬取失败时不中断服务)
  - 可插拔 provider: 真实爬取失败自动回退 Mock

参考: app/services/weather_service.py 的缓存与 Mock 模式.
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import httpx
from loguru import logger

from app.config import settings


# ============================================================
# 数据模型 (dataclass, 阶段三会转成 Pydantic 给 API 用)
# ============================================================

@dataclass
class MarketPriceItem:
    """单条市场价格."""
    crop: str               # 农产品名
    market: str             # 市场名称
    price: float            # 价格 (元/公斤)
    price_unit: str         # 单位
    change: float           # 较昨日涨跌 (元)
    change_percent: float   # 涨跌幅 (%)
    date: str               # 报价日期


@dataclass
class MarketPriceResult:
    """市场价格查询结果."""
    crop: str
    location: str
    items: List[MarketPriceItem] = field(default_factory=list)
    average_price: float = 0.0
    trend: str = "stable"   # up/down/stable
    source: str = "mock"
    update_time: str = ""


@dataclass
class SupplyDemandData:
    """供需分析数据."""
    crop: str
    production: float       # 产量 (万吨)
    consumption: float       # 消费量 (万吨)
    import_volume: float    # 进口 (万吨)
    export_volume: float     # 出口 (万吨)
    stock: float             # 库存 (万吨)
    supply_demand_ratio: float  # 供需比
    analysis: str = ""       # 文字分析
    source: str = "mock"


@dataclass
class PolicySubsidy:
    """单条政策补贴."""
    title: str              # 政策标题
    category: str           # 类别 (种植/养殖/农机/土地/其他)
    subsidy_amount: str     # 补贴标准 (文字描述)
    target: str             # 补贴对象
    conditions: str         # 申报条件
    deadline: str            # 截止日期
    region: str              # 适用地区
    source_url: str          # 来源链接


@dataclass
class PolicyResult:
    """政策补贴查询结果."""
    location: str
    policies: List[PolicySubsidy] = field(default_factory=list)
    source: str = "mock"
    update_time: str = ""


@dataclass
class MarketAnalysisResult:
    """LLM 综合分析结果."""
    crop: str
    location: str
    price_summary: str      # 价格摘要
    trend_forecast: str     # 走势预测
    supply_demand_summary: str  # 供需摘要
    policy_summary: str    # 政策摘要
    sales_advice: str       # 销售建议
    risk_warning: str       # 风险提示
    source: str = "llm"


# ============================================================
# Mock 数据 (爬取失败时兜底, 保证服务可用)
# ============================================================

MOCK_MARKET_PRICES: Dict[str, Dict[str, Any]] = {
    "水稻": {"price": 3.05, "change": 0.02, "percent": 0.66, "trend": "up"},
    "小麦": {"price": 2.78, "change": -0.01, "percent": -0.36, "trend": "down"},
    "玉米": {"price": 2.85, "change": 0.03, "percent": 1.06, "trend": "up"},
    "大豆": {"price": 4.92, "change": 0.05, "percent": 1.03, "trend": "up"},
    "苹果": {"price": 6.50, "change": 0.10, "percent": 1.56, "trend": "up"},
    "番茄": {"price": 3.80, "change": -0.05, "percent": -1.30, "trend": "down"},
    "黄瓜": {"price": 2.50, "change": 0.00, "percent": 0.00, "trend": "stable"},
    "辣椒": {"price": 5.20, "change": 0.15, "percent": 2.97, "trend": "up"},
}

MOCK_SUPPLY_DEMAND: Dict[str, Dict[str, Any]] = {
    "水稻": {"prod": 21000, "cons": 20500, "imp": 400, "exp": 200, "stock": 8500, "ratio": 1.02},
    "小麦": {"prod": 13700, "cons": 13800, "imp": 800, "exp": 100, "stock": 6200, "ratio": 0.99},
    "玉米": {"prod": 28800, "cons": 29000, "imp": 700, "exp": 50, "stock": 12000, "ratio": 0.99},
    "大豆": {"prod": 2000, "cons": 11000, "imp": 9500, "exp": 50, "stock": 3500, "ratio": 0.96},
    "苹果": {"prod": 4500, "cons": 4300, "imp": 50, "exp": 200, "stock": 800, "ratio": 1.05},
    "番茄": {"prod": 6500, "cons": 6400, "imp": 30, "exp": 100, "stock": 200, "ratio": 1.02},
    "黄瓜": {"prod": 5800, "cons": 5750, "imp": 20, "exp": 60, "stock": 150, "ratio": 1.01},
    "辣椒": {"prod": 3200, "cons": 3100, "imp": 40, "exp": 80, "stock": 180, "ratio": 1.03},
}

MOCK_POLICIES: Dict[str, List[Dict[str, Any]]] = {
    "北京": [
        {
            "title": "北京市耕地地力保护补贴",
            "category": "土地",
            "amount": "每亩 150 元",
            "target": "拥有耕地承包权的种地农民",
            "conditions": "耕地不撂荒, 种植作物符合规定",
            "deadline": "每年 6 月 30 日",
            "url": "http://nyncj.beijing.gov.cn",
        },
        {
            "title": "北京市农机购置补贴",
            "category": "农机",
            "amount": "最高 5 万元/台",
            "target": "直接从事农业生产的个人和经营组织",
            "conditions": "购置列入补贴目录的农机具",
            "deadline": "每年 10 月 31 日",
            "url": "http://nyncj.beijing.gov.cn",
        },
    ],
    "山东": [
        {
            "title": "山东省种粮农民直接补贴",
            "category": "种植",
            "amount": "每亩 125 元",
            "target": "实际种粮农民",
            "conditions": "种植粮食作物 (小麦/玉米/水稻)",
            "deadline": "每年 5 月 31 日",
            "url": "http://nync.shandong.gov.cn",
        },
        {
            "title": "山东省设施农业补贴",
            "category": "种植",
            "amount": "每亩 2000-5000 元",
            "target": "新建温室大棚的农户和合作社",
            "conditions": "建设面积 5 亩以上, 符合建设标准",
            "deadline": "每年 8 月 31 日",
            "url": "http://nync.shandong.gov.cn",
        },
    ],
    "上海": [
        {
            "title": "上海市都市现代农业补贴",
            "category": "种植",
            "amount": "每亩 300 元",
            "target": "符合条件的农业经营主体",
            "conditions": "从事都市现代农业生产经营",
            "deadline": "每年 7 月 31 日",
            "url": "http://nyncw.sh.gov.cn",
        },
    ],
}

# 默认政策 (无位置匹配时)
MOCK_DEFAULT_POLICIES: List[Dict[str, Any]] = [
    {
        "title": "耕地地力保护补贴 (全国)",
        "category": "土地",
        "amount": "每亩 100-150 元",
        "target": "拥有耕地承包权的种地农民",
        "conditions": "耕地不撂荒, 种植作物符合规定",
        "deadline": "每年 6 月 30 日",
        "url": "http://www.moa.gov.cn",
    },
    {
        "title": "农机购置补贴 (全国)",
        "category": "农机",
        "amount": "最高 5 万元/台",
        "target": "直接从事农业生产的个人和经营组织",
        "conditions": "购置列入补贴目录的农机具",
        "deadline": "每年 10 月 31 日",
        "url": "http://www.moa.gov.cn",
    },
    {
        "title": "实际种粮农民一次性补贴",
        "category": "种植",
        "amount": "每亩 10-20 元",
        "target": "实际承担农资价格上涨成本的种粮农民",
        "conditions": "当年种植粮食作物",
        "deadline": "每年 8 月 31 日",
        "url": "http://www.moa.gov.cn",
    },
]


def _now_str() -> str:
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _today_str() -> str:
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d")


# ============================================================
# 进程内 TTL 缓存 (价格/供需, 30min)
# ============================================================

class _TTLCache:
    """简单的异步安全 TTL 缓存 (仿 weather_service._WeatherCache)."""

    def __init__(self, ttl_seconds: int = 1800):
        self._ttl = ttl_seconds
        self._store: Dict[str, tuple[float, Any]] = {}
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Optional[Any]:
        async with self._lock:
            entry = self._store.get(key)
            if entry and (time.time() - entry[0]) < self._ttl:
                return entry[1]
            return None

    async def set(self, key: str, value: Any) -> None:
        async with self._lock:
            self._store[key] = (time.time(), value)

    def clear(self) -> None:
        self._store.clear()


_price_cache = _TTLCache(ttl_seconds=1800)      # 30 分钟
_supply_cache = _TTLCache(ttl_seconds=1800)     # 30 分钟
_policy_cache_ttl = 6 * 3600                     # 政策缓存 6 小时


# ============================================================
# Redis 缓存辅助 (政策补贴, 跨进程共享)
# ============================================================

def _policy_cache_key(location: str) -> str:
    return f"market:policy:{location.strip()}"


async def _get_policy_from_redis(location: str) -> Optional[PolicyResult]:
    """从 Redis 读政策缓存, 失败返回 None (不中断)."""
    try:
        from app.core.redis import redis_manager
        raw = await redis_manager.get(_policy_cache_key(location))
        if not raw:
            return None
        data = json.loads(raw)
        policies = [PolicySubsidy(**p) for p in data.get("policies", [])]
        return PolicyResult(
            location=location,
            policies=policies,
            source=data.get("source", "redis_cache"),
            update_time=data.get("update_time", ""),
        )
    except Exception as e:
        logger.debug(f"[Market] Redis 读取政策缓存失败 (忽略): {e}")
        return None


async def _set_policy_to_redis(location: str, result: PolicyResult) -> None:
    """写政策缓存到 Redis, 失败忽略."""
    try:
        from app.core.redis import redis_manager
        payload = {
            "policies": [
                {
                    "title": p.title, "category": p.category,
                    "subsidy_amount": p.subsidy_amount, "target": p.target,
                    "conditions": p.conditions, "deadline": p.deadline,
                    "region": p.region, "source_url": p.source_url,
                }
                for p in result.policies
            ],
            "source": result.source,
            "update_time": result.update_time,
        }
        await redis_manager.set(
            _policy_cache_key(location), payload, expire=_policy_cache_ttl
        )
    except Exception as e:
        logger.debug(f"[Market] Redis 写入政策缓存失败 (忽略): {e}")


# ============================================================
# MarketService 主类
# ============================================================

class MarketService:
    """市场行情服务.

    爬取策略: 真实爬取 (httpx) → 失败回退 Mock.
    缓存策略: 价格/供需用进程内 TTL, 政策用 Redis TTL.
    """

    # 可选的真实爬取数据源 (留接口, 默认走 Mock 保证可用)
    PRICE_API_URL = "http://www.xinfadi.com.cn/api/price"  # 新发地市场价 (示例)
    POLICY_SEARCH_URL = "http://www.moa.gov.cn/gk/zcfg/"   # 农业农村部政策 (示例)

    def __init__(self) -> None:
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=10.0,
                headers={"User-Agent": "AgroAgentOS/1.0 MarketService"},
            )
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    # ============================================================
    # 市场价格
    # ============================================================

    async def get_market_price(
        self, crop: str, location: str = "北京"
    ) -> MarketPriceResult:
        """查询农产品批发市场价格.

        Args:
            crop: 农产品名 (水稻/小麦/玉米/苹果等)
            location: 市场所在城市

        Returns:
            MarketPriceResult, source 标识数据来源 (mock/api)
        """
        cache_key = f"price:{crop}:{location}"
        cached = await _price_cache.get(cache_key)
        if cached:
            logger.debug(f"[Market] 价格命中缓存: {crop}@{location}")
            return cached

        # 尝试真实爬取 (失败自动回退 Mock)
        result = await self._fetch_market_price(crop, location)

        await _price_cache.set(cache_key, result)
        return result

    async def _fetch_market_price(
        self, crop: str, location: str
    ) -> MarketPriceResult:
        """真实爬取市场价格, 失败回退 Mock."""
        # 真实爬取留接口, 当前直接走 Mock 保证服务可用
        # 真实实现需解析 HTML/JSON, 处理反爬, 这里先 Mock
        return self._build_mock_price(crop, location)

    def _build_mock_price(self, crop: str, location: str) -> MarketPriceResult:
        """构建 Mock 价格数据."""
        data = MOCK_MARKET_PRICES.get(crop, MOCK_MARKET_PRICES["水稻"])
        today = _today_str()
        items = [
            MarketPriceItem(
                crop=crop,
                market=f"{location}新发地农产品批发市场",
                price=data["price"],
                price_unit="元/公斤",
                change=data["change"],
                change_percent=data["percent"],
                date=today,
            ),
            MarketPriceItem(
                crop=crop,
                market=f"{location}城北回龙观交易市场",
                price=data["price"] * 1.05,
                price_unit="元/公斤",
                change=data["change"] * 1.1,
                change_percent=data["percent"] * 1.1,
                date=today,
            ),
        ]
        avg = sum(i.price for i in items) / len(items)
        return MarketPriceResult(
            crop=crop, location=location, items=items,
            average_price=round(avg, 2),
            trend=data["trend"],
            source="mock", update_time=_now_str(),
        )

    # ============================================================
    # 供需分析
    # ============================================================

    async def get_supply_demand(self, crop: str) -> SupplyDemandData:
        """查询农产品供需数据."""
        cache_key = f"supply:{crop}"
        cached = await _supply_cache.get(cache_key)
        if cached:
            return cached

        result = self._build_mock_supply(crop)
        await _supply_cache.set(cache_key, result)
        return result

    def _build_mock_supply(self, crop: str) -> SupplyDemandData:
        data = MOCK_SUPPLY_DEMAND.get(crop, MOCK_SUPPLY_DEMAND["水稻"])
        ratio = data["ratio"]
        if ratio > 1.0:
            analysis = f"{crop}供应略大于需求, 价格有下行压力"
        elif ratio < 1.0:
            analysis = f"{crop}需求略大于供应, 价格有支撑"
        else:
            analysis = f"{crop}供需基本平衡, 价格稳定"
        return SupplyDemandData(
            crop=crop,
            production=data["prod"],
            consumption=data["cons"],
            import_volume=data["imp"],
            export_volume=data["exp"],
            stock=data["stock"],
            supply_demand_ratio=ratio,
            analysis=analysis,
            source="mock",
        )

    # ============================================================
    # 政策补贴 (按位置, Redis 缓存 6h)
    # ============================================================

    async def get_policy_subsidies(self, location: str) -> PolicyResult:
        """按位置查询农业政策补贴信息.

        缓存策略: Redis TTL 6h (政策更新频率低, 跨进程共享).
        爬取失败回退 Mock.
        """
        location = location.strip() or "北京"

        # 1. 先查 Redis
        cached = await _get_policy_from_redis(location)
        if cached:
            logger.debug(f"[Market] 政策命中 Redis 缓存: {location}")
            return cached

        # 2. 爬取 (失败回退 Mock)
        result = await self._fetch_policy_subsidies(location)

        # 3. 写 Redis (失败忽略)
        await _set_policy_to_redis(location, result)
        return result

    async def _fetch_policy_subsidies(self, location: str) -> PolicyResult:
        """真实爬取政策补贴, 失败回退 Mock.

        真实实现需爬取各省农业农村厅官网, 当前走 Mock 保证可用.
        """
        return self._build_mock_policy(location)

    def _build_mock_policy(self, location: str) -> PolicyResult:
        """构建 Mock 政策数据."""
        # 按位置匹配, 无匹配用全国默认
        raw_list = MOCK_POLICIES.get(location, MOCK_DEFAULT_POLICIES)
        policies = [
            PolicySubsidy(
                title=p["title"],
                category=p["category"],
                subsidy_amount=p["amount"],
                target=p["target"],
                conditions=p["conditions"],
                deadline=p["deadline"],
                region=location,
                source_url=p["url"],
            )
            for p in raw_list
        ]
        return PolicyResult(
            location=location,
            policies=policies,
            source="mock",
            update_time=_now_str(),
        )

    # ============================================================
    # LLM 综合分析 (价格预测 + 销售建议)
    # ============================================================

    async def get_market_analysis(
        self,
        crop: str,
        location: str,
        price_result: Optional[MarketPriceResult] = None,
        supply_result: Optional[SupplyDemandData] = None,
        policy_result: Optional[PolicyResult] = None,
    ) -> MarketAnalysisResult:
        """LLM 综合分析: 价格预测 + 供需 + 政策 + 销售建议.

        若 LLM 不可用, 回退到规则生成.
        """
        # 自动补齐缺失数据
        if price_result is None:
            price_result = await self.get_market_price(crop, location)
        if supply_result is None:
            supply_result = await self.get_supply_demand(crop)
        if policy_result is None:
            policy_result = await self.get_policy_subsidies(location)

        try:
            return await self._llm_analyze(
                crop, location, price_result, supply_result, policy_result
            )
        except Exception as e:
            logger.warning(
                f"[Market] LLM 分析失败, 回退规则: {type(e).__name__}: {e}"
            )
            return self._rule_based_analyze(
                crop, location, price_result, supply_result, policy_result
            )

    async def _llm_analyze(
        self,
        crop: str,
        location: str,
        price: MarketPriceResult,
        supply: SupplyDemandData,
        policy: PolicyResult,
    ) -> MarketAnalysisResult:
        """调 LLM 生成综合分析."""
        from app.core.llm import get_chat_llm

        price_text = (
            f"当前均价 {price.average_price} 元/公斤, "
            f"趋势 {price.trend}, "
            f"主要市场 {price.items[0].market if price.items else '未知'}"
        )
        supply_text = (
            f"产量 {supply.production} 万吨, 消费 {supply.consumption} 万吨, "
            f"供需比 {supply.supply_demand_ratio}, {supply.analysis}"
        )
        policy_text = "; ".join(
            f"{p.title}({p.subsidy_amount})" for p in policy.policies[:3]
        ) or "暂无相关政策"

        prompt = (
            f"你是农业市场分析专家. 基于以下数据给出 {crop} 在 {location} 的市场分析:\n\n"
            f"【价格行情】{price_text}\n"
            f"【供需数据】{supply_text}\n"
            f"【政策补贴】{policy_text}\n\n"
            f"请输出 Markdown 格式, 包含: 价格摘要、走势预测、供需摘要、"
            f"政策摘要、销售建议、风险提示. 每段不超过 100 字."
        )

        llm = get_chat_llm(temperature=0.3, timeout=30)
        resp = await llm.ainvoke([{"role": "user", "content": prompt}])
        content = resp.content if hasattr(resp, "content") else str(resp)
        if isinstance(content, list):
            content = "".join(
                c.get("text", "") if isinstance(c, dict) else str(c)
                for c in content
            )

        # 简单分段 (LLM 可能不严格按格式, 兜底用规则)
        return self._parse_llm_result(
            content, crop, location, price, supply, policy
        )

    def _parse_llm_result(
        self, content: str, crop: str, location: str,
        price: MarketPriceResult, supply: SupplyDemandData,
        policy: PolicyResult,
    ) -> MarketAnalysisResult:
        """解析 LLM 输出, 失败字段回退规则."""
        def _extract(keyword: str) -> str:
            import re
            m = re.search(
                rf"{keyword}[：:]\s*(.+?)(?=\n#|\n\*\*|$)",
                content, re.DOTALL
            )
            return m.group(1).strip() if m else ""

        rule = self._rule_based_analyze(
            crop, location, price, supply, policy
        )
        return MarketAnalysisResult(
            crop=crop, location=location,
            price_summary=_extract("价格摘要") or rule.price_summary,
            trend_forecast=_extract("走势预测") or rule.trend_forecast,
            supply_demand_summary=_extract("供需摘要") or rule.supply_demand_summary,
            policy_summary=_extract("政策摘要") or rule.policy_summary,
            sales_advice=_extract("销售建议") or rule.sales_advice,
            risk_warning=_extract("风险提示") or rule.risk_warning,
            source="llm",
        )

    def _rule_based_analyze(
        self,
        crop: str,
        location: str,
        price: MarketPriceResult,
        supply: SupplyDemandData,
        policy: PolicyResult,
    ) -> MarketAnalysisResult:
        """规则兜底分析 (LLM 不可用时)."""
        # 价格摘要
        price_summary = (
            f"{crop} 当前均价 {price.average_price} 元/公斤, "
            f"主要市场 {price.items[0].market if price.items else '未知'}."
        )

        # 走势预测
        if price.trend == "up":
            trend_forecast = "近期价格上行, 短期仍有支撑, 建议关注出货时机."
        elif price.trend == "down":
            trend_forecast = "近期价格下行, 建议观望或择机出货."
        else:
            trend_forecast = "近期价格平稳, 可按计划出货."

        # 供需摘要
        if supply.supply_demand_ratio > 1.0:
            supply_summary = f"供应略宽松 (供需比 {supply.supply_demand_ratio}), 价格承压."
        elif supply.supply_demand_ratio < 1.0:
            supply_summary = f"需求略紧 (供需比 {supply.supply_demand_ratio}), 价格有支撑."
        else:
            supply_summary = "供需基本平衡, 价格稳定."

        # 政策摘要
        if policy.policies:
            top = policy.policies[0]
            policy_summary = f"{location} 当前可申请: {top.title} ({top.subsidy_amount})."
        else:
            policy_summary = f"{location} 暂无匹配政策."

        # 销售建议
        if price.trend == "up" and supply.supply_demand_ratio <= 1.0:
            sales_advice = "价格上行且供需偏紧, 建议近期出货, 把握涨价窗口."
        elif price.trend == "down" and supply.supply_demand_ratio > 1.0:
            sales_advice = "价格下行且供应宽松, 建议暂缓出货, 等待价格企稳."
        else:
            sales_advice = "价格平稳, 可按需出货, 关注政策补贴申报窗口."

        # 风险提示
        risk_warning = (
            "注意天气异常、政策调整、国际市场价格波动对 {crop} 价格的影响.".format(
                crop=crop
            )
        )

        return MarketAnalysisResult(
            crop=crop, location=location,
            price_summary=price_summary,
            trend_forecast=trend_forecast,
            supply_demand_summary=supply_summary,
            policy_summary=policy_summary,
            sales_advice=sales_advice,
            risk_warning=risk_warning,
            source="rule",
        )


# ============================================================
# 单例
# ============================================================

_instance: Optional[MarketService] = None


def get_market_service() -> MarketService:
    """获取 MarketService 单例."""
    global _instance
    if _instance is None:
        _instance = MarketService()
        logger.info("[Market] MarketService 已初始化")
    return _instance
