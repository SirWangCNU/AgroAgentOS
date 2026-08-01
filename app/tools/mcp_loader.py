"""工具集合加载器.

负责把"本地 @tool 工具"和"MCP 远程工具"合并成统一的工具列表,
传给 Agent (create_agent) 使用.

设计要点:
  - 本地工具是同步加载 (装饰器自动注册)
  - MCP 工具是异步加载 (在 lifespan 启动时已 connect, 这里直接读已加载列表)
  - 单一入口: agent 只需要 await get_all_tools(), 不用关心来源
"""

from typing import List

from langchain_core.tools import BaseTool
from loguru import logger

from app.core.mcp_client import mcp_client_manager
from app.tools.calendar_tools import generate_planting_calendar, solar_term_reminder
from app.tools.knowledge_tool import search_knowledge_base
from app.tools.market_tool import (
    get_market_analysis,
    get_market_price,
    get_policy_subsidies,
    get_supply_demand,
)
from app.tools.time_tool import get_current_time
from app.tools.weather_tool import get_weather, get_weather_forecast


def get_local_tools() -> List[BaseTool]:
    """返回所有本地 @tool 工具.

    AgroAgentOS 农业工具集:
    - search_knowledge_base: 知识库检索
    - get_current_time: 获取当前时间
    - get_weather: 天气查询与农业建议
    - get_weather_forecast: 7天天气预报与极端天气预警
    - solar_term_reminder: 节气农事提醒
    - generate_planting_calendar: 全年种植历生成
    - get_market_price: 农产品市场价格查询
    - get_supply_demand: 农产品供需分析
    - get_policy_subsidies: 农业政策补贴查询
    - get_market_analysis: 市场综合分析 (价格预测+销售建议)
    """
    return [
        search_knowledge_base,
        get_current_time,
        get_weather,
        get_weather_forecast,
        solar_term_reminder,
        generate_planting_calendar,
        get_market_price,
        get_supply_demand,
        get_policy_subsidies,
        get_market_analysis,
    ]


def get_all_tools() -> List[BaseTool]:
    """返回本地工具 + 已加载的 MCP 工具.

    注意: 必须在 mcp_client_manager.connect() 完成之后调用, 否则只能拿到本地工具.
    通常在 Agent 节点构造时调用一次, 然后缓存.

    返回前会调用 ToolMeta 注册表完整性检查 (§2 cc-haha 借鉴), 把未登记的工具
    打 warning, 帮助开发者及时补 app/tools/meta.py.

    Returns:
        合并后的工具列表
    """
    # 延迟 import 避免循环 (meta -> tools.__init__ -> mcp_loader)
    from app.tools.meta import warn_unregistered_tools

    local = get_local_tools()
    mcp = mcp_client_manager.tools

    # 同名去重: 本地 > MCP (本地实现永远可用, 不依赖 MCP 进程)
    # LangChain create_agent 不允许同名工具, 这里提前合并.
    seen: set[str] = set()
    all_tools: list[BaseTool] = []
    mcp_skipped = 0
    for t in list(local) + list(mcp):
        if t.name in seen:
            mcp_skipped += 1
            continue
        seen.add(t.name)
        all_tools.append(t)
    if mcp_skipped:
        logger.debug(f"工具集合: 跳过 {mcp_skipped} 个 MCP 重名工具 (本地优先)")

    logger.info(f"工具集合: 本地={len(local)} + MCP={len(mcp)} -> 去重后 {len(all_tools)} 个")
    for t in all_tools:
        logger.debug(f"  tool: {t.name} - {(t.description or '')[:60]}")

    # 完整性检查: 任何不在 TOOL_META 中的工具会按保守默认 (非只读 / 不可并发) 处理.
    # 这只是 warning, 不影响功能 - 但会影响 §3 并行优化和 §1 PermissionMode 决策.
    warn_unregistered_tools([t.name for t in all_tools])

    return all_tools
