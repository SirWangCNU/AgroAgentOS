"""MarketService 单元测试.

覆盖:
  - 市场价格查询 (Mock 路径)
  - 供需数据查询
  - 政策补贴查询 (按位置)
  - LLM 综合分析 (规则兜底路径, 不依赖真实 LLM)
  - 进程内 TTL 缓存命中
  - 工具元数据注册完整性

注意: 不依赖 pytest-asyncio, 用 asyncio.run() 包装异步调用.
"""

from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest

from app.services.market_service import (
    MOCK_DEFAULT_POLICIES,
    MOCK_MARKET_PRICES,
    MOCK_POLICIES,
    MOCK_SUPPLY_DEMAND,
    MarketAnalysisResult,
    MarketService,
    MarketPriceResult,
    PolicyResult,
    SupplyDemandData,
    _analysis_cache,
    _get_policy_from_redis,
    _price_cache,
    _supply_cache,
    get_market_service,
)
from app.api.v1 import market as market_api
from app.tools.meta import TOOL_META, get_meta


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture
def service():
    """每个测试用独立的 service 实例, 避免缓存污染."""
    s = MarketService()
    yield s
    _price_cache.clear()
    _supply_cache.clear()
    _analysis_cache.clear()


def _run(coro):
    """同步运行异步协程."""
    return asyncio.run(coro)


# ============================================================
# 市场价格查询
# ============================================================

class TestGetMarketPrice:
    """市场价格查询."""

    def test_known_crop(self, service):
        """已知作物返回正确价格."""
        result = _run(service.get_market_price("水稻", "北京"))
        assert isinstance(result, MarketPriceResult)
        assert result.crop == "水稻"
        assert result.location == "北京"
        assert result.average_price > 0
        assert len(result.items) >= 1
        assert result.source == "mock"
        expected = MOCK_MARKET_PRICES["水稻"]["price"]
        assert result.items[0].price == expected

    def test_unknown_crop_fallback(self, service):
        """未知作物回退到默认 (水稻)."""
        result = _run(service.get_market_price("未知作物", "北京"))
        assert result.crop == "未知作物"
        assert result.items[0].price == MOCK_MARKET_PRICES["水稻"]["price"]

    def test_price_cache_hit(self, service):
        """第二次查询命中缓存."""
        r1 = _run(service.get_market_price("玉米", "北京"))
        assert r1.source == "mock"
        r2 = _run(service.get_market_price("玉米", "北京"))
        assert r2.average_price == r1.average_price
        assert r2.update_time == r1.update_time

    def test_price_unit(self, service):
        """价格单位正确."""
        result = _run(service.get_market_price("苹果", "上海"))
        assert all(item.price_unit == "元/公斤" for item in result.items)


# ============================================================
# 供需数据查询
# ============================================================

class TestGetSupplyDemand:
    """供需数据查询."""

    def test_known_crop(self, service):
        """已知作物返回供需数据."""
        result = _run(service.get_supply_demand("水稻"))
        assert isinstance(result, SupplyDemandData)
        assert result.crop == "水稻"
        assert result.production == MOCK_SUPPLY_DEMAND["水稻"]["prod"]
        assert result.consumption == MOCK_SUPPLY_DEMAND["水稻"]["cons"]
        assert result.supply_demand_ratio == MOCK_SUPPLY_DEMAND["水稻"]["ratio"]
        assert result.analysis
        assert result.source == "mock"

    def test_supply_demand_analysis_text(self, service):
        """供需分析文字根据供需比生成."""
        result = _run(service.get_supply_demand("水稻"))
        assert "供应略大于需求" in result.analysis

        result = _run(service.get_supply_demand("大豆"))
        assert "需求略大于供应" in result.analysis

    def test_supply_cache_hit(self, service):
        """供需数据缓存命中."""
        r1 = _run(service.get_supply_demand("玉米"))
        r2 = _run(service.get_supply_demand("玉米"))
        assert r1.production == r2.production


# ============================================================
# 政策补贴查询 (按位置)
# ============================================================

class TestGetPolicySubsidies:
    """政策补贴查询."""

    def test_policy_redis_cache_reads_decoded_payload(self):
        """Redis 管理器返回已反序列化 dict 时应命中政策缓存."""
        payload = {
            "policies": [
                {
                    "title": "缓存政策",
                    "category": "土地",
                    "subsidy_amount": "每亩 120 元",
                    "target": "实际种植主体",
                    "conditions": "符合耕地保护要求",
                    "deadline": "2026-10-31",
                    "region": "北京",
                    "source_url": "https://example.com/policy",
                }
            ],
            "source": "redis_cache",
            "update_time": "2026-08-10 10:00:00",
        }
        with patch("app.core.redis.redis_manager.get", return_value=payload):
            result = _run(_get_policy_from_redis("北京"))

        assert isinstance(result, PolicyResult)
        assert result.source == "redis_cache"
        assert result.policies[0].title == "缓存政策"

    def test_known_location(self, service):
        """已知位置返回匹配政策."""
        with patch(
            "app.services.market_service._get_policy_from_redis",
            return_value=None,
        ), patch("app.services.market_service._set_policy_to_redis"):
            result = _run(service.get_policy_subsidies("北京"))
        assert isinstance(result, PolicyResult)
        assert result.location == "北京"
        assert len(result.policies) == len(MOCK_POLICIES["北京"])
        assert all(p.region == "北京" for p in result.policies)
        assert result.source == "mock"

    def test_unknown_location_fallback_default(self, service):
        """未知位置回退全国默认政策."""
        with patch(
            "app.services.market_service._get_policy_from_redis",
            return_value=None,
        ), patch("app.services.market_service._set_policy_to_redis"):
            result = _run(service.get_policy_subsidies("未知城市"))
        assert result.location == "未知城市"
        assert len(result.policies) == len(MOCK_DEFAULT_POLICIES)

    def test_empty_location_defaults_beijing(self, service):
        """空位置默认北京."""
        with patch(
            "app.services.market_service._get_policy_from_redis",
            return_value=None,
        ), patch("app.services.market_service._set_policy_to_redis"):
            result = _run(service.get_policy_subsidies(""))
        assert result.location == "北京"

    def test_policy_fields_complete(self, service):
        """政策字段完整."""
        with patch(
            "app.services.market_service._get_policy_from_redis",
            return_value=None,
        ), patch("app.services.market_service._set_policy_to_redis"):
            result = _run(service.get_policy_subsidies("山东"))
        for p in result.policies:
            assert p.title
            assert p.category
            assert p.subsidy_amount
            assert p.target
            assert p.conditions
            assert p.deadline
            assert p.source_url


# ============================================================
# LLM 综合分析 (规则兜底路径)
# ============================================================

class TestGetMarketAnalysis:
    """综合市场分析."""

    def test_analysis_cache_reuses_llm_result(self, service):
        """相同作物和位置的分析应复用缓存, 避免重复调用 LLM."""
        price = _run(service.get_market_price("水稻", "北京"))
        supply = _run(service.get_supply_demand("水稻"))
        with patch(
            "app.services.market_service._get_policy_from_redis",
            return_value=None,
        ), patch("app.services.market_service._set_policy_to_redis"):
            policy = _run(service.get_policy_subsidies("北京"))

        expected = MarketAnalysisResult(
            crop="水稻",
            location="北京",
            price_summary="价格摘要",
            trend_forecast="走势预测",
            supply_demand_summary="供需摘要",
            policy_summary="政策摘要",
            sales_advice="销售建议",
            risk_warning="风险提示",
            source="llm",
        )
        with patch.object(service, "_llm_analyze", return_value=expected) as llm:
            first = _run(service.get_market_analysis("水稻", "北京", price, supply, policy))
            second = _run(service.get_market_analysis("水稻", "北京", price, supply, policy))

        assert first.sales_advice == "销售建议"
        assert second.sales_advice == "销售建议"
        assert llm.call_count == 1

    def test_rule_based_fallback(self, service):
        """LLM 失败时回退规则分析."""
        with patch.object(
            service, "_llm_analyze", side_effect=Exception("LLM unavailable")
        ):
            result = _run(service.get_market_analysis("水稻", "北京"))
        assert result.source == "rule"
        assert result.crop == "水稻"
        assert result.location == "北京"
        assert result.price_summary
        assert result.trend_forecast
        assert result.sales_advice
        assert result.risk_warning

    def test_rule_based_sales_advice_up_trend(self, service):
        """上涨趋势 + 供需偏紧 → 建议出货 (大豆 trend=up ratio=0.96)."""
        with patch.object(
            service, "_llm_analyze", side_effect=Exception("LLM unavailable")
        ):
            result = _run(service.get_market_analysis("大豆", "北京"))
        assert "建议近期出货" in result.sales_advice

    def test_rule_based_sales_advice_down_trend(self, service):
        """下跌趋势 + 供应宽松 → 建议暂缓 (番茄 trend=down ratio=1.02)."""
        with patch.object(
            service, "_llm_analyze", side_effect=Exception("LLM unavailable")
        ):
            result = _run(service.get_market_analysis("番茄", "北京"))
        assert "暂缓出货" in result.sales_advice

    def test_analysis_auto_fetch_data(self, service):
        """未传入数据时自动获取."""
        with patch.object(
            service, "_llm_analyze", side_effect=Exception("LLM unavailable")
        ):
            result = _run(service.get_market_analysis("玉米", "北京"))
        assert result.price_summary


# ============================================================
# 聚合概览 API
# ============================================================

class TestMarketOverviewApi:
    """市场聚合概览接口."""

    def test_overview_can_skip_analysis_for_fast_first_paint(self, service):
        """首屏快数据查询应允许跳过 LLM 综合分析."""
        with patch("app.api.v1.market.get_market_service", return_value=service), \
            patch.object(service, "get_market_analysis", side_effect=AssertionError("LLM should not run")):
            response = _run(
                market_api.get_market_overview(
                    crop="水稻",
                    location="北京",
                    include_analysis=False,
                )
            )

        assert response.data.price is not None
        assert response.data.supply_demand is not None
        assert response.data.policy is not None
        assert response.data.analysis is None


# ============================================================
# 单例
# ============================================================

class TestSingleton:
    """单例测试."""

    def test_get_market_service_singleton(self):
        s1 = get_market_service()
        s2 = get_market_service()
        assert s1 is s2


# ============================================================
# 工具元数据注册完整性
# ============================================================

class TestToolMetaRegistration:
    """工具元数据注册完整性."""

    @pytest.mark.parametrize("tool_name", [
        "get_market_price",
        "get_supply_demand",
        "get_policy_subsidies",
        "get_market_analysis",
    ])
    def test_tool_registered(self, tool_name):
        assert tool_name in TOOL_META, f"{tool_name} 未在 TOOL_META 登记"

    @pytest.mark.parametrize("tool_name", [
        "get_market_price",
        "get_supply_demand",
        "get_policy_subsidies",
        "get_market_analysis",
    ])
    def test_tool_meta_read_only(self, tool_name):
        meta = get_meta(tool_name)
        assert meta.read_only is True, f"{tool_name} 应为 read_only"

    @pytest.mark.parametrize("tool_name", [
        "get_market_price",
        "get_supply_demand",
        "get_policy_subsidies",
        "get_market_analysis",
    ])
    def test_tool_meta_low_risk(self, tool_name):
        meta = get_meta(tool_name)
        assert meta.risk_level == "low", f"{tool_name} 应为 low risk"
