# 农业 Skill 开发指南

Skill 是农业 Agent 的领域能力单元。每个 Skill 用一份 `SKILL.md` 定义触发条件、工具白名单和回答步骤。

## 文件结构

```text
app/skills/definitions/
  agriculture_qa/SKILL.md
  crop_advisory/SKILL.md
  pest_diagnosis/SKILL.md
  weather_advice/SKILL.md
  your_skill/SKILL.md
```

目录名和 `name` 必须使用 snake_case。`agriculture_qa` 是系统兜底 Skill，不应删除。

## Frontmatter

```yaml
---
name: soil_fertility
display_name: 土壤肥力建议
description: 根据土壤与作物信息提供施肥建议
triggers: [土壤, 肥力, 施肥, 有机质]
allowed_tools: [search_knowledge_base, get_weather, get_current_time]
risk_level: low
context: inline
---
```

- `name`：唯一 snake_case 标识，需与目录名一致
- `display_name`：面向用户和日志的名称
- `description`、`triggers`：供 SkillRouter 判断意图
- `allowed_tools`：最小必要工具白名单
- `risk_level`：`low`、`medium` 或 `high`
- `context`：`inline` 使用主图，`fork` 使用独立农业子图

## Playbook

正文应说明适用场景、需要收集的信息、执行步骤、风险边界和输出格式。建议要求模型明确作物、地区、生育期、症状或经营目标；资料不足时先追问，不要编造检测结果、农药登记信息或价格。

## 可用工具

- `search_knowledge_base`：检索农业知识库
- `get_weather`、`get_weather_forecast`：当前天气与预报
- `solar_term_reminder`、`generate_planting_calendar`：农时与种植日历
- `get_market_price`、`get_supply_demand`、`get_policy_subsidies`、`get_market_analysis`：市场与政策
- `get_current_time`：获取真实当前时间
- `web_search`：受限农业联网搜索，是否可用取决于 MCP 配置

## 验证

新增 Skill 后至少运行：

```bash
pytest tests/services/test_agriculture_agent_surface.py -q
pytest
```

启动日志应显示 Skill 成功加载，且未知意图仍可回退到 `agriculture_qa`。
