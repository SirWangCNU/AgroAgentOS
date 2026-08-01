"""农业 Skill 层: 农业智能体的领域 Playbook 抽象.

设计目标:
  - 把农业领域流程从 Prompt 中解耦, 沉淀为可复用、可版本管理的 SKILL.md
  - Planner 基于具体农业 Skill 的 Playbook 制定步骤
  - Executor 工具白名单由 runtime.tool_filter 强制收窄

关键概念:
  - Skill        : 面向某类农业问题的剧本 (例如 pest_diagnosis / weather_advice)
  - SkillRegistry: 启动时加载 app/skills/definitions/ 下所有 SKILL.md, 单例

模块对外接口:
  - get_skill_registry()  : 全局单例
  - Skill, SkillRegistry  : 类型
"""

from app.skills.models import Skill
from app.skills.registry import DEFAULT_SKILL_NAME, SkillRegistry, get_skill_registry

__all__ = [
    "Skill",
    "SkillRegistry",
    "DEFAULT_SKILL_NAME",
    "get_skill_registry",
]
