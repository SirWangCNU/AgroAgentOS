"""工具元数据注册中心 (Tool Metadata Registry).

集中声明每个工具的安全语义和性能语义, 给 Harness / 编排层 / 审计层共享:
  - read_only: 是否只读 (不修改任何外部状态)
  - concurrency_safe: 是否可与同类工具同时并发执行 (一般 read_only=True 才安全)
  - destructive: 是否破坏性 (重启 / 删除 / 不可逆)
  - side_effect: none / external / filesystem / network
  - risk_level: low / medium / high
  - max_result_chars: 工具输出截断阈值 (避免一坨 20KB 日志直接喂 LLM)
  - search_hint: 给未来的 ToolSearch 二级动态发现用

设计原则 (fail-closed):
  - 未在 TOOL_META 登记的工具会拿到保守默认: 不可并发 + 非只读 + 视为有副作用
  - 新增工具时必须在 TOOL_META 里登记, 否则会被并行编排和未来 PermissionMode 默认拦截
  - register_tool_meta() 用于 MCP 等运行时动态加载的工具补登记
"""

from __future__ import annotations

from typing import Callable, Dict, Literal, Optional

from loguru import logger
from pydantic import BaseModel, ConfigDict, Field


SideEffect = Literal["none", "external", "filesystem", "network"]
RiskLevel = Literal["low", "medium", "high"]


class ToolMeta(BaseModel):
    """单个工具的元数据声明.

    所有字段均有保守默认值 (fail-closed). 未声明的工具会被视作:
        read_only=False, concurrency_safe=False, destructive=False, side_effect=none

    这意味着未登记的工具:
      - 在并行编排里只会串行执行 (安全)
      - 在 ASK_DESTRUCTIVE 模式下会被默认 ASK (因为 read_only=False)
    """

    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=False)

    read_only: bool = Field(
        default=False,
        description="不修改任何外部状态 (只读查询).",
    )
    concurrency_safe: bool = Field(
        default=False,
        description="多实例同时并发调用不会相互干扰; 一般 read_only=True 才安全.",
    )
    destructive: bool = Field(
        default=False,
        description="不可逆操作 (重启 / 删除 / 扣款); 通常 ASK_DESTRUCTIVE 模式下需人工确认.",
    )
    side_effect: SideEffect = Field(
        default="none",
        description="副作用类别: none / external / filesystem / network.",
    )
    is_notification: bool = Field(
        default=False,
        description="是否为外发通知类工具.",
    )
    risk_level: RiskLevel = Field(
        default="low",
        description="风险等级: low (只读查询) / medium (外发通知 / 联网) / high (写操作).",
    )
    max_result_chars: int = Field(
        default=16000,
        description="工具结果上限字符数, 超过后由编排层截断或落盘.",
    )
    search_hint: Optional[str] = Field(
        default=None,
        description="供 ToolSearch 二级动态发现使用的关键字.",
    )

    # 输入参数感知 (例如 Bash 工具按命令决定是否只读). 当前不强求实现, 占位.
    is_read_only_for_input: Optional[Callable[[dict], bool]] = Field(
        default=None,
        description="可选: 根据输入决定是否只读, 优先于 read_only 字段.",
    )

    def effective_read_only(self, tool_input: Optional[dict] = None) -> bool:
        """根据输入计算最终的只读判定; 异常时回退静态 read_only 字段."""
        if self.is_read_only_for_input is not None and tool_input is not None:
            try:
                return bool(self.is_read_only_for_input(tool_input))
            except Exception as exc:  # pragma: no cover - 防御式
                logger.debug(
                    f"[ToolMeta] is_read_only_for_input 抛错, 回退静态 read_only={self.read_only}: {exc}"
                )
        return self.read_only


# ============================================================
# 中央注册表 (农业智农协同平台)
# ============================================================
TOOL_META: Dict[str, ToolMeta] = {
    # ===== 农业知识库 =====
    "search_knowledge_base": ToolMeta(
        read_only=True,
        concurrency_safe=True,
        max_result_chars=8000,
        risk_level="low",
        search_hint="rag knowledge base 知识库 农业 种植 养殖",
    ),

    # ===== 时间工具 =====
    "get_current_time": ToolMeta(
        read_only=True,
        concurrency_safe=True,
        max_result_chars=200,
        risk_level="low",
        search_hint="time clock 时间 日期 农时",
    ),

    # ===== 天气工具 =====
    "get_weather": ToolMeta(
        read_only=True,
        concurrency_safe=True,
        max_result_chars=3000,
        risk_level="low",
        search_hint="weather 天气 气温 湿度 降雨 农事",
    ),

    # ===== 天气预报工具 =====
    "get_weather_forecast": ToolMeta(
        read_only=True,
        concurrency_safe=True,
        max_result_chars=5000,
        risk_level="low",
        search_hint="forecast 预报 预警 霜冻 暴雨 高温 干旱 7天",
    ),

    # ===== 节气提醒工具 =====
    "solar_term_reminder": ToolMeta(
        read_only=True,
        concurrency_safe=True,
        max_result_chars=4000,
        risk_level="low",
        search_hint="solar term 节气 农时 二十四节气 农事提醒",
    ),

    # ===== 种植历工具 =====
    "generate_planting_calendar": ToolMeta(
        read_only=True,
        concurrency_safe=True,
        max_result_chars=6000,
        risk_level="low",
        search_hint="calendar 种植历 种植计划 全年安排 播种期",
    ),

    # ===== 联网搜索 =====
    "web_search": ToolMeta(
        read_only=True,
        concurrency_safe=False,  # 外部搜索应避免被 LLM 批量打爆
        side_effect="network",
        max_result_chars=12000,
        risk_level="medium",
        search_hint="web search internet 联网 搜索 农业资料",
    ),

    # ===== 市场行情工具 =====
    "get_market_price": ToolMeta(
        read_only=True,
        concurrency_safe=True,
        max_result_chars=6000,
        risk_level="low",
        search_hint="market price 价格 行情 农产品 批发价",
    ),
    "get_supply_demand": ToolMeta(
        read_only=True,
        concurrency_safe=True,
        max_result_chars=4000,
        risk_level="low",
        search_hint="supply demand 供需 产量 库存 进出口",
    ),
    "get_policy_subsidies": ToolMeta(
        read_only=True,
        concurrency_safe=True,
        max_result_chars=6000,
        risk_level="low",
        search_hint="policy subsidy 政策 补贴 惠农 申报",
    ),
    "get_market_analysis": ToolMeta(
        read_only=True,
        concurrency_safe=True,
        max_result_chars=8000,
        risk_level="low",
        search_hint="analysis 预测 建议 销售 走势",
    ),

    # ===== Lazy MCP 元工具 =====
    "mcp_search_tools": ToolMeta(
        read_only=True,
        concurrency_safe=True,
        max_result_chars=4000,
        risk_level="low",
        search_hint="mcp search tools 搜索工具",
    ),
    "mcp_execute_tool": ToolMeta(
        read_only=False,
        concurrency_safe=False,
        side_effect="external",
        risk_level="medium",
        max_result_chars=20000,
        search_hint="mcp execute call 调用工具",
    ),

    # ===== 二级 Agent (Subagent) delegate 工具 =====
    "delegate_to_kb_researcher": ToolMeta(
        read_only=True,
        concurrency_safe=True,
        side_effect="network",  # 内部可能联网
        risk_level="medium",
        max_result_chars=6000,
        search_hint="knowledge research 知识检索 农业知识",
    ),
}


# ============================================================
# 公共 API
# ============================================================
_CONSERVATIVE_DEFAULT = ToolMeta()  # read_only=False, concurrency_safe=False, ...


def get_meta(tool_name: str) -> ToolMeta:
    """查询工具元数据.

    未登记的工具返回保守默认 (read_only=False / concurrency_safe=False),
    确保 fail-closed 安全语义.
    """
    return TOOL_META.get(tool_name, _CONSERVATIVE_DEFAULT)


def is_registered(tool_name: str) -> bool:
    """判断工具是否在中央注册表中显式登记 (排除保守默认兜底)."""
    return tool_name in TOOL_META


def register_tool_meta(tool_name: str, meta: ToolMeta, *, override: bool = False) -> None:
    """运行时补登记元数据 (例如 MCP 工具加载完成后).

    Args:
        tool_name: 工具名称
        meta: 元数据
        override: 已存在时是否覆盖, 默认 False (避免误改静态声明)
    """
    if not override and tool_name in TOOL_META:
        logger.debug(f"[ToolMeta] {tool_name} 已存在静态声明, 不覆盖 (传 override=True 强制)")
        return
    TOOL_META[tool_name] = meta
    logger.debug(f"[ToolMeta] 注册 {tool_name}: read_only={meta.read_only} risk={meta.risk_level}")


def warn_unregistered_tools(tool_names: list[str]) -> list[str]:
    """对一批工具名做登记完整性检查, 返回未登记的子集 (并打 warning).

    建议在 get_all_tools() 加载完毕后调用一次, 帮助开发者发现新增工具忘记登记的情况.
    """
    missing = [name for name in tool_names if name not in TOOL_META]
    if missing:
        logger.warning(
            f"[ToolMeta] 以下工具未在 TOOL_META 登记, 将按保守默认 (非只读 / 不可并发) 处理: "
            f"{sorted(missing)}. 请在 app/tools/meta.py 补登记, 否则会影响并行编排和 PermissionMode 决策."
        )
    return missing


def summarize_registry() -> dict:
    """生成注册表汇总 (用于 /api 健康检查或启动日志).

    Returns:
        dict: 各 risk_level / read_only / concurrency_safe 的工具数和示例.
    """
    by_risk: Dict[str, list[str]] = {"low": [], "medium": [], "high": []}
    read_only_count = 0
    concurrency_safe_count = 0
    for name, meta in TOOL_META.items():
        by_risk[meta.risk_level].append(name)
        if meta.read_only:
            read_only_count += 1
        if meta.concurrency_safe:
            concurrency_safe_count += 1
    return {
        "total_registered": len(TOOL_META),
        "read_only": read_only_count,
        "concurrency_safe": concurrency_safe_count,
        "by_risk": {k: sorted(v) for k, v in by_risk.items()},
    }
