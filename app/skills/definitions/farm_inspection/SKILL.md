---
name: farm_inspection
display_name: 农场综合巡检
description: 基于农场快照、天气风险、田间作业质量和待办任务生成待人工确认的巡检提案
triggers:
  - 农场巡检
  - 综合巡检
  - 暴雨风险
allowed_tools:
  - get_farm_snapshot
  - inspect_farm_weather_risks
  - get_field_work_quality
  - get_pending_farm_tasks
  - search_knowledge_base
  - create_action_proposal
risk_level: medium
context: inline
icon: Radar
category: 风险防控
tagline: 主动发现农场风险并生成待确认提案
examples:
  - 帮我巡检一下海淀农场
  - 最近暴雨对我的农场有什么影响？
  - 生成一份农场综合巡检报告
---

# 农场综合巡检

## 适用场景

- 对指定农场执行综合巡检。
- 评估暴雨、排水、田间作业质量及重复任务风险。
- 形成供农场负责人审核的行动提案。

## 证据顺序

必须按以下顺序工作，前一步的数据缺口要带入后续分析：

1. 调用 `get_farm_snapshot`，确认农场、地块、作物阶段、数据时效和缺失项。
2. 调用 `inspect_farm_weather_risks`，读取实测或预报的天气风险及其观测时间。
3. 调用 `get_field_work_quality`，核对轨迹覆盖、作业质量和异常点。
4. 调用 `get_pending_farm_tasks`，排除已有待办与重复行动。
5. 需要阈值或农艺依据时调用 `search_knowledge_base`，并保留来源。
6. 只有完成上述证据核对后，才可调用 `create_action_proposal`。

## 证据标注

- **实测事实（`measured`）**：工具直接返回的农场、天气、轨迹、任务数据；写明来源和时间。
- **规则依据（`rule`）**：知识库中的阈值、作物阶段要求或验收规则；写明引用来源。
- **分析推断（`inference`）**：由事实与规则推导出的风险判断；明确不确定性和待补证据。

没有证据不得生成高置信度提案。证据冲突、过期或缺失时，降低置信度并在数据缺口中标记需要人工复核，不得用常识补齐成实测事实。

## 提案边界

- `create_action_proposal` 仅创建待人工确认的提案，状态必须保持 `pending`。
- 不批准、不派发、不执行农事任务，不把提案描述为已生效。
- 行动应包含截止时间、责任建议和可验证的验收条件，并避免与已有待办重复。

## 输出格式

先输出结构化提案摘要：风险、严重度、置信度、实测事实、规则依据、分析推断、建议行动、截止时间、验收条件和数据缺口。最后明确提示：提案仍为 `pending`，需要人工确认后才能进入执行流程。
