---
name: farm_task_verification
display_name: 农事任务验收
description: 基于任务证据、田间作业质量和验收规则生成只供人工审核的验收草稿
triggers:
  - 农事任务验收
  - 作业验收
  - 任务核验
allowed_tools:
  - get_task_evidence
  - get_field_work_quality
  - search_knowledge_base
  - save_task_verification_draft
risk_level: medium
context: inline
icon: ClipboardCheck
category: 风险防控
tagline: 依据证据自动复核农事作业质量
examples:
  - 帮我验收最近的施肥任务
  - 这个喷药任务的轨迹覆盖合格吗？
  - 生成任务验收草稿
---

# 农事任务验收

## 适用场景

- 核验指定农事任务的执行材料、轨迹和质量数据。
- 依据任务验收条件形成机器建议，交由人工最终审核。

## 证据顺序

1. 调用 `get_task_evidence`，读取任务要求、执行记录、附件、时间戳和证据缺口。
2. 调用 `get_field_work_quality`，核对轨迹覆盖、作业参数和异常点。
3. 只有任务自身规则不完整时才调用 `search_knowledge_base` 补充农艺规则，并保留来源；知识库不能替代任务的明确验收条件。
4. 完成证据比较后，调用 `save_task_verification_draft` 保存验收草稿。

## 证据标注

- **实测事实（`measured`）**：任务记录、附件、轨迹和质量工具直接返回的数据。
- **规则依据（`rule`）**：任务验收条件优先，其次才是有来源的知识库规则。
- **分析推断（`inference`）**：事实与规则之间的比较结果；明确不确定性和缺口。

没有证据不得给出高置信度结论。缺少关键证明时选择 `needs_evidence`；证据明确不满足验收条件且需要返工时选择 `rework`；证据冲突、规则含糊或必须由人判断时选择 `manual_review`。不得猜测任务已完成。

## verdict 合同

- `pass`：关键验收条件均有一致且可追溯的证据支持。
- `needs_evidence`：缺少完成验收所需的关键证明，需要补交证据。
- `rework`：证据明确表明验收条件未满足，需要重新作业或整改。
- `manual_review`：证据冲突、规则含糊或存在工具无法判断的情况，需要人工裁决。

## 草稿边界

保存草稿不改变任务状态。`save_task_verification_draft` 只记录机器建议，不通过、不驳回、不关闭任务，也不替代最终审核。

## 输出格式

输出任务标识、`verdict`、置信度、实测事实、规则依据、分析推断、未满足项、数据缺口和人工复核建议，并明确说明本次结果仅为验收草稿，最终审核由人工完成。
