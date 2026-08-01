# AgroAgentOS 系统架构

AgroAgentOS 是面向农业生产与经营的 FastAPI + LangGraph 多智能体平台。系统不提供服务器监控、告警接收、日志排障、容器管理或其他 AIOps 能力。

## 请求入口

所有业务 API 挂载在 `/api/v1`：

- `chat`：农业问答与 SSE 流式响应
- `image`：农作物图片分析
- `farms`：农场与地块管理
- `market`：农产品市场信息
- `video`：农业营销内容生成
- `documents`：农业知识文档管理
- `history`、`sessions`：问答历史与会话
- `auth`、`health`、`skills`：认证、健康检查与技能查询

## Agent 流程

主图由 `build_agriculture_graph()` 构建：

```text
START -> SkillRouter -> Planner -> Executor -> Replanner -> END
                                      ^             |
                                      +-------------+
```

`SkillRouter` 从 `app/skills/definitions/` 选择农业 Skill。未命中或模型输出无效时回退到 `agriculture_qa`。`Planner` 读取 Skill playbook，`Executor` 调用该 Skill 白名单中的农业工具，`Replanner` 判断继续执行还是汇总结果。

当前 Skill 包括通用农业问答、种植建议、病虫害分析、天气建议、市场情报、营销生成和知识检索。

## 工具与外部能力

本地工具集中在 `app/tools/`，提供农业知识库、天气、农事日历、市场和当前时间。MCP 仅保留天气与受限联网搜索能力。联网搜索面向农业、气象、市场、政策和科研资料，并拦截娱乐、隐私与敏感凭据查询。

## 数据存储

- SQLite 或 MySQL：用户、农场、地块、会话、问答历史等结构化数据
- Redis：按会话保存短期对话记忆，不保存跨会话诊断报告
- Milvus：农业知识文档与用户主动上传的问答记录向量
- `knowledge_base/`：农业知识库原始文档

历史数据库文件可能仍含早期的 `agent_runs`、`agent_execution_logs` 实体表。当前 ORM、业务代码和数据迁移脚本均不再引用它们；物理删表应通过单独的数据迁移执行，避免直接破坏现有农业数据库。

## 前端

`frontend-react/` 使用 React 19、Vite、Zustand 和 TanStack Query。前端通过 `/api` 代理访问 FastAPI，生产构建由 FastAPI 静态托管。
