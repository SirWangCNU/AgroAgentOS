# 农业 Skill 系统

Skill 将农业领域的处理步骤从通用 Prompt 中拆出，存放在
`app/skills/definitions/<name>/SKILL.md`。启动时 `SkillRegistry` 自动扫描定义；
Router 选择失败或命中未知名称时统一回退到 `agriculture_qa`。

每份定义由 YAML frontmatter 和 Markdown playbook 组成。`allowed_tools` 必须只列出完成该农业任务所需的工具，名称与 `app/tools/mcp_loader.py` 实际注册结果一致。

详细格式与验证方法见 `docs/skill_development_guide.md`。
