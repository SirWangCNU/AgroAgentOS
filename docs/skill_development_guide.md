# 农业 Skill 开发指南

本文说明 AgroAgentOS 农业 Skill 的格式、证据约束和验证方式。

## 运行方式

Skill 文件位于 `app/skills/definitions/<skill_name>/SKILL.md`。启动时 `SkillRegistry` 自动扫描文件；Router 选择 Skill，Planner 读取 playbook，Executor 按工具白名单执行，Replanner 评估证据并收敛。

`agriculture_qa` 是农业领域的硬 fallback，不得删除。未知 Skill 名或路由失败时，注册表必须回退到它。

## Frontmatter

```yaml
---
name: farm_inspection
display_name: 农场综合巡检
description: 基于农场证据生成待人工确认的巡检提案
triggers:
  - 农场巡检
allowed_tools:
  - get_farm_snapshot
risk_level: medium
context: inline
---
```

| 字段 | 要求 |
|---|---|
| `name` | 必填，唯一的 snake_case 名称 |
| `display_name` | 必填，面向用户的名称 |
| `description` | 必填，写清适用场景和边界 |
| `triggers` | 可选，Router 使用的自然语言触发词 |
| `allowed_tools` | 工具硬白名单，名称必须与运行时注册一致 |
| `risk_level` | `low`、`medium` 或 `high` |
| `context` | `inline` 或 `fork` |

## Farm Skill 合同

### `farm_inspection`

工具白名单必须精确为：

```text
get_farm_snapshot
inspect_farm_weather_risks
get_field_work_quality
get_pending_farm_tasks
search_knowledge_base
create_action_proposal
```

证据顺序是农场快照、天气风险、田间作业质量、已有待办、知识规则，最后才创建行动提案。提案只能保持 `pending`，必须提示人工确认。

### `farm_task_verification`

工具白名单必须精确为：

```text
get_task_evidence
get_field_work_quality
search_knowledge_base
save_task_verification_draft
```

先核对任务证据和作业质量，再按需补充知识规则，最后保存验收草稿。`verdict` 只能是 `pass`、`fail` 或 `needs_review`。保存草稿不改变任务状态，最终审核由人工完成。

## Playbook 证据规范

正文必须明确三类信息：

- 实测事实（`measured`）：工具直接返回的数据，注明来源与时间。
- 规则依据（`rule`）：任务验收条件或有来源的知识库规则。
- 分析推断（`inference`）：由事实和规则推导的判断，注明不确定性。

没有证据不得生成高置信度提案或验收结论。证据缺失、过期或冲突时应降低置信度、列出数据缺口，并选择人工复核路径。

## 二级 Agent

农业工作流提供三个委托角色：

| Agent | 职责 |
|---|---|
| `farm_data_analyst` | 只收集农场、地块、轨迹和任务事实 |
| `agronomy_researcher` | 研究天气、知识库、作物阶段和不确定性 |
| `farm_work_planner` | 草拟行动、截止时间和验收条件，不做最终审批 |

对应工具名为 `delegate_to_<agent_type>`，新增或改名时必须同步 `app/tools/meta.py`。

## 验证

```powershell
$env:PYTHONPATH=(Get-Location).Path
$env:DEBUG='false'
pytest tests/skills/test_farm_agent_skills.py tests/agents/test_agriculture_prompts.py -q
```

测试必须验证 fallback、精确工具白名单、证据顺序、草稿边界、二级 Agent 名称以及提示词遗留语义扫描。
