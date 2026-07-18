# AgroAgentOS Skill 层

Skill 是农业 Agent 的场景 playbook：Router 选择 Skill，Planner 读取正文，Executor 只能使用 `allowed_tools`，Replanner 基于证据决定继续、切换或生成报告。

## 农业 fallback

`agriculture_qa` 是硬 fallback。Router 返回未知名称、调用失败或无法为农业问题确定更具体场景时，`SkillRegistry.get_or_generic()` 都回退到它。该 Skill 必须存在。

## Farm Skills

| Skill | 用途 | 写入边界 |
|---|---|---|
| `farm_inspection` | 依次核对农场快照、天气风险、作业质量、待办任务和农艺依据 | 仅创建 `pending` 行动提案，等待人工确认 |
| `farm_task_verification` | 核对任务证据、作业质量和验收规则 | 仅保存验收草稿，不改变任务状态 |

两个 playbook 都必须：

1. 先取证，再推断，最后才允许写草稿。
2. 区分实测事实、规则依据和分析推断。
3. 证据不足时降低置信度并说明数据缺口。
4. 不批准、不派发、不执行任务，最终决策由人工完成。

## 文件布局

```text
app/skills/
  models.py
  loader.py
  registry.py
  definitions/
    agriculture_qa/SKILL.md
    farm_inspection/SKILL.md
    farm_task_verification/SKILL.md
```

Skill 文件使用 YAML frontmatter 加 Markdown 正文。完整字段和验证方式见 `docs/skill_development_guide.md`。
