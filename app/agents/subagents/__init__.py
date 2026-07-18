"""农业二级 Agent 注册中心.

主执行器可以把事实收集、农艺研究和行动草拟委托给三个职责明确的助手；
每个助手只能访问其白名单内的工具，最终决策仍由主流程和人工完成。
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class SubagentDefinition(BaseModel):
    """单个二级 Agent 的定义."""

    agent_type: str = Field(..., description="Subagent 唯一标识, 用于 delegate_to_<type>")
    display_name: str = Field(..., description="人类可读名称, 日志/前端展示")
    description: str = Field(
        ...,
        description="给主 Executor LLM 看的委托边界说明",
    )
    system_prompt: str = Field(..., description="Subagent 自己的 system prompt")
    allowed_tools: List[str] = Field(
        default_factory=list,
        description="Subagent 能用的真实工具白名单",
    )
    max_iters: int = Field(default=3, description="Subagent 内部 LLM 与工具往返上限")
    max_result_chars: int = Field(default=8000, description="返回结果字符上限")


SUBAGENTS: dict[str, SubagentDefinition] = {
    "farm_data_analyst": SubagentDefinition(
        agent_type="farm_data_analyst",
        display_name="农场数据分析助手",
        description=(
            "只收集并整理指定农场、地块、轨迹和任务事实。适合核对农场快照、"
            "田间作业质量、待办任务或任务证据；不做农艺规则解释、行动建议或审批。"
        ),
        system_prompt=(
            "你是农场数据分析助手，只收集农场、地块、轨迹和任务事实。\n"
            "所有结论必须能追溯到工具返回值，并注明数据时间和缺失项。\n"
            "只汇报实测事实，不引入外部规则，不做风险推断、行动建议或审批。\n"
            "数据冲突时并列呈现，不自行选择看起来更合理的一项。"
        ),
        allowed_tools=[
            "get_farm_snapshot",
            "get_field_work_quality",
            "get_pending_farm_tasks",
            "get_task_evidence",
        ],
        max_iters=3,
        max_result_chars=8000,
    ),
    "agronomy_researcher": SubagentDefinition(
        agent_type="agronomy_researcher",
        display_name="农艺研究助手",
        description=(
            "研究天气风险、作物阶段和知识库规则，适合补充有来源的农艺依据并说明"
            "不确定性；不把规则当实测数据，也不创建或批准任务。"
        ),
        system_prompt=(
            "你是农艺研究助手，负责天气、知识库、作物阶段和不确定性分析。\n"
            "先读取农场作物阶段与天气风险，再按需检索知识库。\n"
            "严格区分实测事实、规则依据和分析推断，每条规则注明来源。\n"
            "资料不足或冲突时明确不确定性，不生成无证据的高置信度判断。"
        ),
        allowed_tools=[
            "get_farm_snapshot",
            "inspect_farm_weather_risks",
            "search_knowledge_base",
        ],
        max_iters=3,
        max_result_chars=8000,
    ),
    "farm_work_planner": SubagentDefinition(
        agent_type="farm_work_planner",
        display_name="农事行动规划助手",
        description=(
            "把主流程提供的已核验证据整理为行动、截止时间和验收条件。"
            "不收集新证据，不创建任务，不做最终审批。"
        ),
        system_prompt=(
            "你是农事行动规划助手，根据 task 中已有且注明来源的证据草拟方案。\n"
            "每项方案必须包含行动、截止时间和验收条件，并标注依赖的数据缺口。\n"
            "不得补写未提供的事实，不创建或派发任务，不做最终审批。\n"
            "输出必须说明方案需由人工确认后才能执行。"
        ),
        allowed_tools=[],
        max_iters=1,
        max_result_chars=8000,
    ),
}


def get_subagent(agent_type: str) -> Optional[SubagentDefinition]:
    """按 agent_type 取定义, 不存在返回 None."""
    return SUBAGENTS.get(agent_type)
