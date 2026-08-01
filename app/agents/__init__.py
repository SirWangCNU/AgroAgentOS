"""LangGraph 主图入口。

Plan-Execute-Replan 三段式：
  Planner    -> 把农业问题拆为多步计划
  Executor   -> 执行单步, 调工具 (支持只读并行)
  Replanner  -> 看结果, 决定继续 / 替换计划 / 收尾

详细图结构见 graph.py, 状态见 state.py。
"""

from app.agents.graph import build_agriculture_graph
from app.agents.state import PlanExecuteState

__all__ = ["build_agriculture_graph", "PlanExecuteState"]
