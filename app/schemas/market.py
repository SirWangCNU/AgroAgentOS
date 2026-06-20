"""市场行情相关数据模型 (Pydantic, 供 API 序列化用)."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


# ============================================================
# 市场价格
# ============================================================

class MarketPriceItem(BaseModel):
    """单条市场价格."""
    crop: str = Field(..., description="农产品名")
    market: str = Field(..., description="市场名称")
    price: float = Field(..., description="价格 (元/公斤)")
    price_unit: str = Field(..., description="单位")
    change: float = Field(..., description="较昨日涨跌 (元)")
    change_percent: float = Field(..., description="涨跌幅 (%)")
    date: str = Field(..., description="报价日期")


class MarketPriceData(BaseModel):
    """市场价格查询结果."""
    crop: str
    location: str
    items: List[MarketPriceItem] = Field(default_factory=list)
    average_price: float = Field(default=0.0, description="均价 (元/公斤)")
    trend: str = Field(default="stable", description="趋势: up/down/stable")
    source: str = Field(default="mock")
    update_time: str = Field(default="")


# ============================================================
# 供需数据
# ============================================================

class SupplyDemandData(BaseModel):
    """供需分析数据."""
    crop: str
    production: float = Field(..., description="产量 (万吨)")
    consumption: float = Field(..., description="消费量 (万吨)")
    import_volume: float = Field(..., description="进口 (万吨)")
    export_volume: float = Field(..., description="出口 (万吨)")
    stock: float = Field(..., description="库存 (万吨)")
    supply_demand_ratio: float = Field(..., description="供需比")
    analysis: str = Field(default="", description="文字分析")
    source: str = Field(default="mock")


# ============================================================
# 政策补贴
# ============================================================

class PolicySubsidy(BaseModel):
    """单条政策补贴."""
    title: str
    category: str = Field(..., description="类别: 种植/养殖/农机/土地/其他")
    subsidy_amount: str = Field(..., description="补贴标准")
    target: str = Field(..., description="补贴对象")
    conditions: str = Field(..., description="申报条件")
    deadline: str = Field(..., description="截止日期")
    region: str = Field(..., description="适用地区")
    source_url: str = Field(..., description="来源链接")


class PolicyData(BaseModel):
    """政策补贴查询结果."""
    location: str
    policies: List[PolicySubsidy] = Field(default_factory=list)
    source: str = Field(default="mock")
    update_time: str = Field(default="")


# ============================================================
# 综合分析
# ============================================================

class MarketAnalysisData(BaseModel):
    """LLM 综合分析结果."""
    crop: str
    location: str
    price_summary: str
    trend_forecast: str
    supply_demand_summary: str
    policy_summary: str
    sales_advice: str
    risk_warning: str
    source: str = Field(default="llm")


# ============================================================
# 聚合概览 (前端工作台用)
# ============================================================

class MarketOverview(BaseModel):
    """市场行情聚合概览 (价格+供需+政策+分析)."""
    crop: str
    location: str
    price: Optional[MarketPriceData] = None
    supply_demand: Optional[SupplyDemandData] = None
    policy: Optional[PolicyData] = None
    analysis: Optional[MarketAnalysisData] = None
