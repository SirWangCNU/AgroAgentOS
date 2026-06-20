"""市场行情 API 端点 - 供前端调用.

GET /api/v1/market/price?crop=水稻&location=北京    - 市场价格
GET /api/v1/market/supply-demand?crop=水稻          - 供需数据
GET /api/v1/market/policy?location=北京             - 政策补贴 (按位置)
GET /api/v1/market/analysis?crop=水稻&location=北京  - 综合分析
GET /api/v1/market/overview?crop=水稻&location=北京  - 聚合概览
"""

from __future__ import annotations

from fastapi import APIRouter, Query
from loguru import logger

from app.schemas.common import ApiResponse
from app.schemas.market import (
    MarketAnalysisData,
    MarketOverview,
    MarketPriceData,
    MarketPriceItem,
    PolicyData,
    PolicySubsidy,
    SupplyDemandData,
)
from app.services.location_service import resolve_location
from app.services.market_service import get_market_service

router = APIRouter(prefix="/market", tags=["market"])


def _current_user_id() -> int | None:
    """从当前请求获取 user_id (简化版, 后续可接 JWT 依赖).

    当前返回 None, 让 resolve_location 走默认城市.
    未来接入 auth 依赖后替换为真实 user_id.
    """
    return None


@router.get(
    "/price",
    summary="获取农产品市场价格",
    description="查询指定农产品在指定城市的批发市场价格",
)
async def get_market_price(
    crop: str = Query(default="水稻", description="农产品名"),
    location: str = Query(default="", description="城市名 (空则用用户农场位置)"),
):
    location = resolve_location(location, _current_user_id())
    logger.info(f"[market-api] 查询价格: crop={crop} location={location}")

    service = get_market_service()
    result = await service.get_market_price(crop, location)

    return ApiResponse.success(
        data=MarketPriceData(
            crop=result.crop,
            location=result.location,
            items=[
                MarketPriceItem(
                    crop=i.crop, market=i.market, price=i.price,
                    price_unit=i.price_unit, change=i.change,
                    change_percent=i.change_percent, date=i.date,
                )
                for i in result.items
            ],
            average_price=result.average_price,
            trend=result.trend,
            source=result.source,
            update_time=result.update_time,
        ),
        message="价格查询成功",
    )


@router.get(
    "/supply-demand",
    summary="获取农产品供需数据",
    description="查询指定农产品的产量、消费、进出口、库存等供需数据",
)
async def get_supply_demand(
    crop: str = Query(default="水稻", description="农产品名"),
):
    logger.info(f"[market-api] 查询供需: crop={crop}")

    service = get_market_service()
    result = await service.get_supply_demand(crop)

    return ApiResponse.success(
        data=SupplyDemandData(
            crop=result.crop,
            production=result.production,
            consumption=result.consumption,
            import_volume=result.import_volume,
            export_volume=result.export_volume,
            stock=result.stock,
            supply_demand_ratio=result.supply_demand_ratio,
            analysis=result.analysis,
            source=result.source,
        ),
        message="供需查询成功",
    )


@router.get(
    "/policy",
    summary="获取农业政策补贴 (按位置)",
    description="根据用户所在地区查询可申请的农业政策补贴信息",
)
async def get_policy_subsidies(
    location: str = Query(default="", description="城市/地区名 (空则用用户农场位置)"),
):
    location = resolve_location(location, _current_user_id())
    logger.info(f"[market-api] 查询政策: location={location}")

    service = get_market_service()
    result = await service.get_policy_subsidies(location)

    return ApiResponse.success(
        data=PolicyData(
            location=result.location,
            policies=[
                PolicySubsidy(
                    title=p.title, category=p.category,
                    subsidy_amount=p.subsidy_amount, target=p.target,
                    conditions=p.conditions, deadline=p.deadline,
                    region=p.region, source_url=p.source_url,
                )
                for p in result.policies
            ],
            source=result.source,
            update_time=result.update_time,
        ),
        message="政策查询成功",
    )


@router.get(
    "/analysis",
    summary="获取市场综合分析",
    description="基于价格、供需、政策数据生成价格预测和销售建议",
)
async def get_market_analysis(
    crop: str = Query(default="水稻", description="农产品名"),
    location: str = Query(default="", description="城市名 (空则用用户农场位置)"),
):
    location = resolve_location(location, _current_user_id())
    logger.info(f"[market-api] 综合分析: crop={crop} location={location}")

    service = get_market_service()
    result = await service.get_market_analysis(crop, location)

    return ApiResponse.success(
        data=MarketAnalysisData(
            crop=result.crop,
            location=result.location,
            price_summary=result.price_summary,
            trend_forecast=result.trend_forecast,
            supply_demand_summary=result.supply_demand_summary,
            policy_summary=result.policy_summary,
            sales_advice=result.sales_advice,
            risk_warning=result.risk_warning,
            source=result.source,
        ),
        message="分析生成成功",
    )


@router.get(
    "/overview",
    summary="获取市场行情聚合概览",
    description="一次性返回价格+供需+政策+综合分析 (前端工作台用)",
)
async def get_market_overview(
    crop: str = Query(default="水稻", description="农产品名"),
    location: str = Query(default="", description="城市名 (空则用用户农场位置)"),
):
    location = resolve_location(location, _current_user_id())
    logger.info(f"[market-api] 聚合概览: crop={crop} location={location}")

    service = get_market_service()

    # 并行获取四类数据
    import asyncio
    price_task = service.get_market_price(crop, location)
    supply_task = service.get_supply_demand(crop)
    policy_task = service.get_policy_subsidies(location)
    price_r, supply_r, policy_r = await asyncio.gather(
        price_task, supply_task, policy_task
    )
    # 分析依赖前三者, 串行
    analysis_r = await service.get_market_analysis(
        crop, location, price_r, supply_r, policy_r
    )

    overview = MarketOverview(
        crop=crop,
        location=location,
        price=MarketPriceData(
            crop=price_r.crop, location=price_r.location,
            items=[
                MarketPriceItem(
                    crop=i.crop, market=i.market, price=i.price,
                    price_unit=i.price_unit, change=i.change,
                    change_percent=i.change_percent, date=i.date,
                )
                for i in price_r.items
            ],
            average_price=price_r.average_price,
            trend=price_r.trend,
            source=price_r.source,
            update_time=price_r.update_time,
        ),
        supply_demand=SupplyDemandData(
            crop=supply_r.crop, production=supply_r.production,
            consumption=supply_r.consumption, import_volume=supply_r.import_volume,
            export_volume=supply_r.export_volume, stock=supply_r.stock,
            supply_demand_ratio=supply_r.supply_demand_ratio,
            analysis=supply_r.analysis, source=supply_r.source,
        ),
        policy=PolicyData(
            location=policy_r.location,
            policies=[
                PolicySubsidy(
                    title=p.title, category=p.category,
                    subsidy_amount=p.subsidy_amount, target=p.target,
                    conditions=p.conditions, deadline=p.deadline,
                    region=p.region, source_url=p.source_url,
                )
                for p in policy_r.policies
            ],
            source=policy_r.source, update_time=policy_r.update_time,
        ),
        analysis=MarketAnalysisData(
            crop=analysis_r.crop, location=analysis_r.location,
            price_summary=analysis_r.price_summary,
            trend_forecast=analysis_r.trend_forecast,
            supply_demand_summary=analysis_r.supply_demand_summary,
            policy_summary=analysis_r.policy_summary,
            sales_advice=analysis_r.sales_advice,
            risk_warning=analysis_r.risk_warning,
            source=analysis_r.source,
        ),
    )

    return ApiResponse.success(data=overview, message="行情概览获取成功")
