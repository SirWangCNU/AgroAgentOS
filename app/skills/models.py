"""Skill 数据模型.

每个 Skill 由一个 SKILL.md 文件描述, 格式为 YAML frontmatter + Markdown body:

    ---
    name: soil_fertility
    display_name: 土壤肥力建议
    description: 根据土壤和作物信息提供施肥与改良建议
    triggers: [土壤, 肥力, 施肥, 有机质]
    allowed_tools: [search_knowledge_base, get_weather, get_current_time]
    risk_level: low
    ---

    # 土壤肥力建议
    ## 适用场景
    ...
    ## 推荐排查步骤
    1. ...
    ## 输出格式
    ...

frontmatter 字段约束见 Skill 模型, body 原样保留到 Skill.playbook.
"""

from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator

# 风险等级:
#   low    = 仅读操作（查知识库、天气、市场数据）
#   medium = 调用外部 API, 但不写状态
#   high   = 涉及外部写入或不可逆业务操作，必须经 Harness 人工确认
RiskLevel = Literal["low", "medium", "high"]

# §4 cc-haha 借鉴: Skill 执行模式
#   inline = playbook 注入主对话，主图 plan-execute-replan 直接执行
#   fork   = 起独立子图跑完整 plan-execute-replan, 仅回传 final answer 给主线
#            适用: 未来长报告 / 联网研究 / 双语通告等长任务 Skill
SkillContextMode = Literal["inline", "fork"]


class Skill(BaseModel):
    """单个 Skill 的运行时表示.

    实例由 loader.load_skill_from_file 从 SKILL.md 解析得到.
    """

    # ===== frontmatter 字段 =====
    name: str = Field(..., description="Skill 唯一标识，snake_case，例如 soil_fertility")
    display_name: str = Field(..., description="人类可读名称, 用于日志和前端展示")
    description: str = Field(..., description="适用场景一句话描述, 给 Skill Router 看")
    triggers: List[str] = Field(
        default_factory=list,
        description="触发关键字, 用于启发式匹配 (本期仅作 Router 提示, 不参与硬匹配)",
    )
    allowed_tools: List[str] = Field(
        default_factory=list,
        description="允许 Executor 调用的工具白名单. 第一版仅作记录, Harness 阶段强制",
    )
    risk_level: RiskLevel = Field(
        default="low",
        description="风险等级, Harness 用于决定是否需要人工确认",
    )
    # ===== §4 inline / fork 字段 =====
    context: SkillContextMode = Field(
        default="inline",
        description=(
            "执行模式: inline (默认, playbook 注入主对话) / "
            "fork (独立子图跑, 只回传 final answer). "
            "fork 适合写报告/联网研究等容易污染主对话的长任务."
        ),
    )
    fork_max_iters: int = Field(
        default=4,
        description="fork 模式下子图的最大 plan-execute-replan 循环次数",
    )

    # ===== Markdown body =====
    playbook: str = Field(
        default="",
        description="完整 Markdown body, 包含适用场景/推荐排查步骤/输出格式等",
    )
    source_path: Optional[str] = Field(default=None, description="源 SKILL.md 文件路径")

    @field_validator("name")
    @classmethod
    def _name_snake_case(cls, v: str) -> str:
        if not v or not v.replace("_", "").isalnum():
            raise ValueError(f"skill name 必须是 snake_case (仅字母数字下划线): {v!r}")
        return v.lower()

    def to_router_card(self) -> str:
        """生成给 Skill Router LLM 看的菜单条目 (Markdown)."""
        triggers = ", ".join(self.triggers) if self.triggers else "(无)"
        return (
            f"- **{self.name}** — {self.display_name}\n"
            f"  适用场景: {self.description}\n"
            f"  触发关键字: {triggers}"
        )
