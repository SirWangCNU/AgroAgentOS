# AgroAgentOS 农业生产 Copilot 比赛版改造设计

**日期**：2026-07-24  
**状态**：已废弃；由 `2026-07-24-farm-copilot-full-rebuild-design.md` 替代
**目标赛事**：第八届中国研究生人工智能创新大赛  
**推荐赛题**：开放赛题一“生成式大语言模型与智能体”，应用创意类

## 1. 决策摘要

AgroAgentOS 从“农场巡检与任务闭环系统”调整为：

> 面向家庭农场、合作社和农业社会化服务组织，由农场主和农艺师直接使用的多模态农业生产 Copilot。

比赛版不再把“巡检、提案、审批、任务、AI 验收”作为产品主流程。用户通过文字、语音或照片与一个农场助手交互，系统结合农场、地块、作物、生育期、天气、历史农事和农业知识，生成三类可直接使用的结果：

1. 结构化农事记录；
2. 有证据的地块级建议；
3. 简单提醒和生产总结。

改造采用中度重构：

- 保留农场数据、天气、图像识别、RAG、Agent 运行时和安全工具机制；
- 新建 Farm Copilot 应用层和单一主工作台；
- 接通新主流程后，删除旧提案、审批、任务验收运行链；
- 不删除历史 Alembic 迁移；
- 旧业务表先保留为无运行时引用的历史表，避免比赛前执行破坏性数据迁移。

## 2. 背景与问题

### 2.1 当前产品的问题

当前 Farm Agent 的主要流程是：

```text
综合巡检
→ 风险识别
→ 创建行动提案
→ 人工批准或拒绝
→ 生成农事任务
→ 提交执行证据
→ AI 复核
→ 人工完成或退回
```

这套流程具有审计性，但存在三个产品问题：

1. 对普通农场主过重。农场主经常同时承担决策和执行，不需要审批自己的建议。
2. 对大型农业企业又不完整。系统没有完整的组织租户、农场级成员权限、库存采购、供应链、合规和外部系统集成。
3. 比赛演示主线过长。初赛视频不超过五分钟，当前十步闭环难以在有限时间内突出 AI 推理效果和场景价值。

### 2.2 目标用户

核心经营主体：

- 50 至 1000 亩家庭农场；
- 农民合作社；
- 农业社会化服务组织；
- 管理多个地块的小型种植企业。

核心使用者：

- 农场主；
- 生产负责人；
- 农艺师。

次要使用者：

- 现场作业人员，只接收简单提醒或查看农事要求，不进入完整管理后台。

### 2.3 用户核心问题

比赛版只解决以下高频问题：

1. 今天哪些地块最值得关注？
2. 今天是否适合灌溉、施肥或喷药？
3. 作物照片反映了什么问题？
4. 一句话能否完成农事记录？
5. 最近做过什么，接下来什么时候复查？
6. 本周有哪些风险、农事和投入？

## 3. 目标与非目标

### 3.1 产品目标

1. 用户进入系统后十秒内看到“今日最重要的三件事”。
2. 用户用一句自然语言完成一条可编辑、可确认的结构化农事记录。
3. 图片诊断必须结合地块上下文，而不是只对图片进行通用识别。
4. 农艺建议必须展示数据依据、知识来源、置信度和不确定性。
5. 建议可以一键转成简单提醒，但不进入审批和任务验收状态机。
6. 比赛演示在五分钟内完整呈现多模态、上下文、工具调用、记忆和行动价值。
7. 建立可重复运行的评测集，提交 AI 推理效果和指标。

### 3.2 工程目标

1. 删除旧闭环运行时代码和不再使用的前端交互。
2. 将农场上下文、农事记录、农艺建议、简报和提醒分别集中在职责单一的业务模块中。
3. 简单请求使用确定性业务路径，复杂咨询才进入 Agent 规划，降低时延和失败率。
4. 保持路由、业务逻辑、外部适配、Schema 和 UI 状态分层。
5. 保留旧数据的读取安全，不在比赛前自动删除历史业务表。

### 3.3 明确不做

比赛版不实现：

- 多级审批；
- 复杂农事工单状态机；
- AI 任务验收；
- 完整农资库存和采购；
- 完整成本会计；
- 供应链追溯；
- 企业级多租户和细粒度 RBAC；
- 自动控制灌溉设备或无人机；
- 自动执行施药等高风险操作；
- 同时覆盖所有作物；
- 将模型思维链直接展示给用户；
- 将市场行情、视频生成等能力放入核心演示。

## 4. 方案选择

评估三种方案：

### 4.1 方案 A：仅替换前端

隐藏提案、任务和验收，在现有接口上拼接新页面。

优点：

- 开发最快；
- 数据库和后端改动少。

缺点：

- 后端仍围绕旧闭环组织；
- Schema、工具和测试继续携带无用复杂度；
- 后续维护仍需理解提案和任务状态机。

### 4.2 方案 B：中度重构

新建 Farm Copilot 应用层，复用已有基础能力；接通后删除旧闭环运行链。

优点：

- 产品主流程和代码结构一致；
- 可以删除大量无用代码；
- 复用现有可靠能力；
- 比赛前风险可控。

缺点：

- 需要同步修改前端、接口、业务模块、Agent 工具和测试；
- 需要一个短期兼容阶段。

### 4.3 方案 C：全面重写

重新设计数据模型、Agent 图和全部页面。

优点：

- 理论上最干净。

缺点：

- 在 2026-09-01 提交截止前风险过高；
- 容易丢失现有测试、安全控制和演示可复现性。

采用方案 B。

## 5. 核心用户体验

### 5.1 信息架构

比赛版主导航收敛为：

```text
今日
农场
记录
报告
```

说明：

- “今日”是默认首页，也是 Farm Copilot 主工作台；
- “农场”维护农场、地块、作物和生育期；
- “记录”查看和修正农事事件；
- “报告”查看周报、风险和简单投入摘要；
- 天气、病虫害诊断和知识库作为 Copilot 的内部能力，不再要求用户切换多个独立页面；
- 管理员用户管理保留在管理员菜单，不进入比赛主线。

### 5.2 主工作台

桌面端布局：

```text
┌────────────────────────────────────────────────────────────┐
│ 农场选择 / 地块选择 / 当前作物与生育期 / 天气摘要          │
├──────────────┬──────────────────────────┬──────────────────┤
│ 地块列表     │ 今日关注                 │ 最近农事         │
│ 作物状态     │ Copilot 对话与结果卡     │ 待办提醒         │
│ 简要地图     │ 文字 / 语音 / 照片输入   │ 数据完整度       │
└──────────────┴──────────────────────────┴──────────────────┘
```

移动端按以下顺序纵向排列：

1. 农场和地块选择；
2. 今日关注；
3. Copilot 输入；
4. 建议或记录结果；
5. 提醒和最近农事。

### 5.3 快捷操作

主输入框上方只提供六个快捷操作：

- 记录农事；
- 今天做什么；
- 拍照诊断；
- 灌溉建议；
- 施肥建议；
- 生成周报。

### 5.4 输出卡片

#### 农事记录草稿卡

包含：

- 地块；
- 农事类型；
- 时间；
- 投入品、亩用量和总量；
- 操作人；
- 原始语句；
- 缺失字段；
- 编辑、确认保存、取消。

记录在用户确认后写入 `FarmEvent`。比赛版不允许 LLM 在没有展示结构化草稿的情况下静默写入农事记录。

#### 农艺建议卡

包含：

- 结论；
- 适用农场和地块；
- 建议动作；
- 推荐时间窗口；
- 风险等级；
- 置信度；
- 数据依据；
- 知识来源；
- 数据缺口和不确定性；
- 设置提醒。

#### 图片诊断卡

包含：

- 图片识别结果；
- 可能问题及概率；
- 地块、作物和生育期；
- 与近期天气和农事记录的联合判断；
- 需要补充的信息；
- 建议动作；
- 安全提示；
- 设置复查提醒。

#### 今日简报卡

最多显示三项主要关注事项。每项包含：

- 地块；
- 原因；
- 建议；
- 时间窗口；
- 证据状态。

不能用十几条低优先级提醒淹没用户。

## 6. 业务流程

### 6.1 统一交互入口

```text
用户输入
→ 意图识别
→ 加载可信农场上下文
→ 选择确定性路径或 Agent 路径
→ 证据与安全检查
→ 生成结构化结果卡
→ 用户确认记录或创建提醒
```

支持的意图固定为：

- `record_activity`
- `ask_advice`
- `diagnose_image`
- `get_daily_brief`
- `create_reminder`
- `get_weekly_report`

无法识别时返回最多三个可选意图，不进入无上限自由规划。

### 6.2 简单业务路径

以下请求不进入 Planner/Replanner：

- 保存用户已确认的农事记录；
- 查询近期农事；
- 创建、完成和取消提醒；
- 读取已生成的简报；
- 生成纯统计型周报；
- 读取农场和地块上下文。

这些路径由业务模块直接处理，保证可预测性和低时延。

### 6.3 复杂 Agent 路径

以下请求进入现有 Agent 运行时：

- 跨天气、农事历史和知识库的综合建议；
- 图片、作物阶段和近期投入的联合诊断；
- 数据缺失时需要重新选择工具的复杂咨询。

复杂路径继续遵守：

```text
SkillRouter → Planner → Executor → Replanner
```

但比赛版 Skill 收敛为：

- `farm_advice`
- `crop_diagnosis`

`farm_recording`、`farm_brief` 和 `farm_report` 使用业务模块，不伪装成多步骤 Agent。

### 6.4 证据检查

建议生成后必须执行以下检查：

1. 是否存在农场和地块归属上下文；
2. 建议引用的数据是否真实存在；
3. 实测、规则、外部知识和模型推断是否明确区分；
4. 数据时间是否过期；
5. 施药或投入品建议是否有可靠来源；
6. 置信度是否与数据完整度匹配；
7. 是否需要提示用户补充信息。

证据检查失败时返回降级建议或补充问题，不能伪造完整结论。

## 7. 后端模块设计

### 7.1 `farm_context_service`

职责：

- 校验当前用户拥有目标农场；
- 聚合农场、地块、当前茬次、作物、生育期；
- 聚合近期 `FarmEvent`、传感器读数和天气；
- 标记数据时间和数据缺口；
- 返回统一的 `FarmContext` Schema。

复用：

- `farm_snapshot_service`
- `farm_run_query_service.require_owned_farm`
- `weather_service`

其接口是所有 Copilot 建议和简报的可信上下文入口。其他模块不得各自重新拼接农场上下文。

### 7.2 `farm_record_service`

职责：

- 将模型解析结果校验为 `FarmRecordDraft`；
- 校验地块归属、事件类型、时间和投入品单位；
- 返回缺失字段；
- 在用户确认后写入 `FarmEvent`；
- 使用 `client_request_id` 保证重复确认不会重复写入。

模型解析失败时保留用户原始文本，不返回虚假成功。

### 7.3 `farm_advice_service`

职责：

- 接收用户问题和 `FarmContext`；
- 决定是否需要复杂 Agent 路径；
- 调用天气、知识、图片和农场只读工具；
- 生成结构化 `FarmAdvice`；
- 执行证据检查和安全降级；
- 将运行摘要写入 `AgentRun.outcome_json`。

该模块不创建提案，不创建任务，不自动执行农业操作。

### 7.4 `farm_brief_service`

职责：

- 使用确定性规则筛选今日关注项；
- 按风险、时间窗口和数据完整度排序；
- 最多返回三项；
- 可选调用 LLM 将结构化事项转成简短自然语言；
- LLM 不可用时仍返回规则结果。

### 7.5 `farm_reminder_service`

职责：

- 创建简单提醒；
- 列出待办和已完成提醒；
- 完成或取消提醒；
- 校验农场和地块归属；
- 支持来源为用户创建、建议卡或简报。

提醒只有以下状态：

```text
pending → done
pending → cancelled
```

不提供开始、提交、验收、退回等状态。

### 7.6 `farm_report_service`

职责：

- 汇总一周内农事事件；
- 汇总投入品数量和已知成本；
- 汇总建议、提醒完成情况和数据缺口；
- 输出结构化周报；
- 可选用 LLM 生成一段简短总结。

比赛版不做完整财务核算。没有单价的数据只汇总数量，不估算成本。

## 8. 数据模型

### 8.1 保留

- `Farm`
- `Field`
- `CropSeason`
- `SensorReading`
- `FarmEvent`
- `AgentRun`
- 用户、会话和知识库相关模型

### 8.2 新增 `FarmReminder`

建议字段：

| 字段 | 含义 |
|---|---|
| `id` | 数据库主键 |
| `reminder_id` | 对外 UUID，唯一 |
| `farm_id` | 所属农场 |
| `field_id` | 可选地块 |
| `created_by` | 创建用户 |
| `title` | 提醒标题 |
| `note` | 补充说明 |
| `due_at` | 提醒时间 |
| `status` | `pending/done/cancelled` |
| `source` | `manual/advice/brief` |
| `source_ref` | 可选 AgentRun 或建议引用 |
| `created_at` | 创建时间 |
| `completed_at` | 完成时间 |

### 8.3 不新增持久化 Advice 表

建议结果保存在：

- 当前交互响应；
- 会话消息；
- `AgentRun.outcome_json`。

只有用户选择“设置提醒”时才新增 `FarmReminder`。避免为所有模型回答建立额外业务表。

### 8.4 删除旧运行时模型

新主流程接通后，从 ORM 和运行时代码中删除：

- `FarmActionProposal`
- `FarmTask`

保留：

- 历史迁移 `007_add_farm_agent_workflow.py`；
- 已存在数据库中的 `farm_action_proposals` 和 `farm_tasks` 表；
- `FarmEvent.related_task_id` 作为可空历史字段。

比赛前不自动 Drop 表。赛后如确认历史数据无需保留，再单独设计可回滚的数据清理迁移。

## 9. 接口设计

新增路由前缀：

```text
/api/v1/farm-copilot
```

### 9.1 今日简报

```http
GET /api/v1/farm-copilot/today?farm_id={farm_id}&field_id={field_id?}
```

返回：

- 农场上下文摘要；
- 最多三项今日关注；
- 待办提醒；
- 最近农事。

### 9.2 统一交互

```http
POST /api/v1/farm-copilot/interactions/stream
```

输入：

- `farm_id`
- 可选 `field_id`
- `message`
- 可选已上传图片引用
- 可选显式意图

SSE 事件只保留用户可理解的状态：

```text
start
context_loaded
analyzing
source_found
result
complete
error
```

详细节点和工具轨迹写入 `AgentRun`，通过评委模式查询，不占据主界面。

### 9.3 农事记录

```http
POST /api/v1/farm-copilot/records/parse
POST /api/v1/farm-copilot/records
GET  /api/v1/farm-copilot/records
```

`parse` 只生成草稿，不写数据库；`records` 在用户确认后写入 `FarmEvent`。

### 9.4 提醒

```http
POST /api/v1/farm-copilot/reminders
GET  /api/v1/farm-copilot/reminders
POST /api/v1/farm-copilot/reminders/{reminder_id}/complete
POST /api/v1/farm-copilot/reminders/{reminder_id}/cancel
```

### 9.5 周报

```http
GET /api/v1/farm-copilot/reports/weekly?farm_id={farm_id}&week={YYYY-Www}
```

### 9.6 评委模式

```http
GET /api/v1/farm-copilot/runs/{run_id}/timeline
```

只用于比赛技术说明和调试，普通工作台默认不展示。

## 10. 前端模块设计

### 10.1 新增

```text
frontend-react/src/pages/FarmCopilot.tsx
frontend-react/src/api/farmCopilot.ts
frontend-react/src/types/farmCopilot.ts
frontend-react/src/stores/farmCopilot.ts
frontend-react/src/components/farm-copilot/FarmContextBar.tsx
frontend-react/src/components/farm-copilot/TodayBrief.tsx
frontend-react/src/components/farm-copilot/CopilotInput.tsx
frontend-react/src/components/farm-copilot/RecordDraftCard.tsx
frontend-react/src/components/farm-copilot/AdviceCard.tsx
frontend-react/src/components/farm-copilot/ReminderList.tsx
frontend-react/src/components/farm-copilot/RecentFarmRecords.tsx
frontend-react/src/components/farm-copilot/JudgeTraceDrawer.tsx
```

说明：

- `FarmCopilot.tsx` 只编排页面数据和交互；
- API 与 SSE 解析集中在 `api/farmCopilot.ts`；
- 服务端状态使用 React Query；
- 当前流式交互和草稿状态使用 `stores/farmCopilot.ts`；
- 记录卡、建议卡和提醒列表分别处理自身空、错、加载和成功状态。

### 10.2 路由与导航

- `/` 默认进入 Farm Copilot；
- 新主路由为 `/workspace/farm-copilot`；
- `/workspace/farms` 保留；
- 通用 Chat 不再是默认入口；
- 独立天气、病虫害和知识页面从比赛主导航移除，但底层能力保留；
- 市场行情不进入比赛主导航；
- 管理员用户管理只对管理员显示。

### 10.3 比赛演示数据

演示场景注入不再出现在普通主界面。

保留版本化场景 fixture 和注入模块，用于：

- 自动化测试；
- 比赛前预置演示农场；
- 断网或外部数据不可用时的可复现演示。

正常界面只显示“演示数据”来源标识，不提供评委面前手动注入传感器数据的操作。

## 11. 删除与瘦身计划

删除必须在新主流程接通并通过测试后执行。

### 11.1 前端删除

删除旧页面和仅服务于旧闭环的模块：

```text
frontend-react/src/pages/FarmAgent.tsx
frontend-react/src/components/farm-agent/ActionProposalCard.tsx
frontend-react/src/components/farm-agent/HumanApprovalBar.tsx
frontend-react/src/components/farm-agent/InspectionStepper.tsx
frontend-react/src/components/farm-agent/FarmTaskBoard.tsx
frontend-react/src/components/farm-agent/TaskVerificationCard.tsx
frontend-react/src/components/farm-agent/CurrentInsightCard.tsx
frontend-react/src/api/farmTasks.ts
```

以下模块根据新页面实际复用情况迁移后删除或重命名：

```text
frontend-react/src/components/farm-agent/AgentRunTimeline.tsx
frontend-react/src/components/farm-agent/FarmEventTimeline.tsx
frontend-react/src/stores/farmAgent.ts
frontend-react/src/api/farmAgent.ts
frontend-react/src/types/farmAgent.ts
```

删除所有 `.bak` 页面文件和确认未被导入的旧视频生成前端残留。

### 11.2 后端删除

新接口接通后删除：

```text
app/api/v1/farm_tasks.py
app/services/farm_proposal_service.py
app/services/farm_task_service.py
app/skills/definitions/farm_task_verification/SKILL.md
```

重构后删除旧文件：

```text
app/api/v1/farm_agent.py
app/services/farm_agent_service.py
app/schemas/farm_agent.py
```

这些文件中仍需要的运行查询、事件查询、茬次查询、传感器查询和 SSE 包装逻辑，先迁移到职责对应的新模块，禁止复制后保留两份。

### 11.3 工具瘦身

从 Agent 工具注册中删除：

- `get_pending_farm_tasks`
- `get_task_evidence`
- `create_action_proposal`
- `save_task_verification_draft`

保留并迁移到 `farm_copilot_tools.py`：

- 农场上下文读取；
- 天气风险读取；
- 农业知识检索；
- 图片分析；
- 近期农事读取；
- 提醒草稿生成所需的只读信息。

Agent 不直接写入农事记录和提醒。写入操作经业务接口的用户确认完成。

### 11.4 Agent 与 Skill 瘦身

删除：

- `farm_task_verification` Skill；
- `task_verification` 运行类型；
- 任务验收专用图分支；
- 提案和任务相关二级 Agent 工具权限；
- ToolMeta 中对应旧工具定义。

将 `farm_inspection` 替换为：

- `farm_advice`
- `crop_diagnosis`

两个 Skill 的工具白名单必须精确且默认只读。

### 11.5 测试处理

删除功能对应的旧测试可以在功能代码删除时一并移除，但必须新增：

- 旧提案和任务接口返回 404 的迁移测试；
- 新 Copilot 记录、建议、简报和提醒测试；
- 旧闭环符号在运行时代码中不再出现的扫描测试；
- 历史迁移仍能从空数据库升级成功的测试。

不删除历史 Alembic 迁移测试中对版本 007 的兼容验证，除非新增迁移明确替代其职责。

## 12. 错误处理与降级

### 12.1 缺少农场

返回创建农场入口，不启动 Agent。

### 12.2 缺少地块

对地块级问题只询问一次目标地块；用户未选择时不猜测。

### 12.3 缺少作物或生育期

降低建议置信度，并提示补充作物或生育期。

### 12.4 天气不可用

- 今日简报继续返回非天气事项；
- 建议卡标记天气证据缺失；
- 不输出确定的喷药或灌溉时间窗口。

### 12.5 知识库不可用

- 保留实测数据和规则结果；
- 不输出需要专业知识支持的确定剂量；
- 标记知识证据不可用。

### 12.6 图片质量不足

返回重拍建议，包括光线、距离和叶片正反面要求，不强行诊断。

### 12.7 LLM 不可用

- 农场上下文、近期农事、提醒和规则简报仍可用；
- 已输入的记录原文保留；
- 不伪造解析或建议成功。

### 12.8 重复提交

记录和提醒写入接受 `client_request_id`，重复请求返回原结果。

## 13. 安全与可信性

1. 所有接口使用认证用户并校验农场归属。
2. Agent 工具从可信运行上下文获取用户和农场，不接受模型自由填写身份。
3. 高风险农业建议只给建议，不自动控制设备或执行作业。
4. 农药、剂量、安全间隔期必须有可靠知识来源；没有来源时要求咨询当地农技人员或查看标签。
5. 用户可看到结论依据和数据时间，但不展示模型隐式思维链。
6. 上传图片遵循现有文件类型、大小和访问控制。
7. 日志不记录完整敏感输入、Token 或用户隐私数据。

## 14. 评测设计

大赛提交规范要求体现 AI 推理效果和指标。新增：

```text
evals/farm_copilot/
  record_extraction_cases.json
  advice_grounding_cases.json
  risk_scenarios.json
  diagnosis_cases.json
  run_evals.py
  README.md
```

### 14.1 农事记录提取

数据：

- 200 条中文农事口语；
- 覆盖施肥、灌溉、喷药、播种、巡田和收获；
- 包含缺字段、口语单位和模糊时间。

指标：

- 意图准确率；
- 字段级 Precision、Recall、F1；
- 完整记录 Exact Match；
- 缺失字段识别准确率。

目标：

- 意图准确率不低于 95%；
- 关键字段 F1 不低于 90%；
- 不完整输入不得静默补造关键字段。

### 14.2 建议证据一致性

数据：

- 100 个农场上下文和问题组合；
- 包含天气缺失、作物缺失、近期刚操作和证据冲突。

指标：

- 证据覆盖率；
- 不支持结论率；
- 数据时间引用正确率；
- 应降级场景正确降级率。

目标：

- 证据覆盖率不低于 95%；
- 不支持结论率低于 5%；
- 应降级场景正确降级率不低于 95%。

### 14.3 风险场景

沿用并整理暴雨、干旱、虫害和缺肥场景。

指标：

- 风险识别 Precision、Recall、F1；
- 风险等级准确率；
- 重复运行一致性。

### 14.4 图片诊断

在有授权的数据上评测：

- Top-1 和 Top-3 命中率；
- 低质量图片拒答率；
- 加入地块上下文前后的判断改进；
- 无法确认时的安全降级率。

不得使用来源不明的图片作为公开比赛数据。

### 14.5 基线对比

至少比较：

1. 通用大模型；
2. 只有农业 RAG、没有农场上下文；
3. AgroAgentOS Farm Copilot。

重点证明农场上下文、工具调用和长期农事记忆带来的提升。

## 15. 五分钟比赛演示

### 15.1 时间分配

| 时间 | 内容 |
|---|---|
| 0:00-0:35 | 农场经营痛点与产品定位 |
| 0:35-1:05 | 今日简报主动发现问题 |
| 1:05-1:45 | 一句话生成结构化农事记录 |
| 1:45-2:50 | 上传黄叶照片并联合上下文诊断 |
| 2:50-3:25 | 查看证据、置信度并设置提醒 |
| 3:25-4:10 | 评委模式展示工具调用和运行轨迹 |
| 4:10-4:40 | 与通用大模型和普通 RAG 的指标对比 |
| 4:40-5:00 | 社会价值、商业对象和结束语 |

### 15.2 主演示故事

1. 水稻农场主打开今日简报，系统提示 A1 地块需要关注，并显示不利天气窗口。
2. 用户说：“昨天 A1 地块追了尿素，每亩五公斤。”
3. 系统生成结构化记录草稿，用户确认后保存。
4. 用户上传 A1 地块黄叶照片。
5. Copilot 联合图片、生育期、刚保存的施肥记录、天气和知识库，输出有证据的判断。
6. 用户设置第二天复查提醒。
7. 评委模式展示本次运行调用了哪些真实工具和数据。

## 16. 验收标准

### 16.1 产品验收

1. 默认首页是 Farm Copilot，而不是通用 Chat 或旧驾驶舱。
2. 用户可在一个页面完成今日查看、农事记录、咨询、图片诊断和提醒。
3. 记录必须经过结构化草稿确认。
4. 建议必须展示证据、置信度和数据缺口。
5. 天气、知识库或 LLM 失败时有明确降级。
6. 普通页面不出现提案审批、任务验收和复杂状态机。
7. 比赛演示无需在现场手动注入场景数据。

### 16.2 代码瘦身验收

运行时代码中不再存在：

```text
FarmActionProposal
FarmTask
farm_proposal_service
farm_task_service
farm_task_verification
save_task_verification_draft
create_action_proposal
get_pending_farm_tasks
```

前端不再存在旧提案、审批、任务看板和验收组件。

保留历史迁移和旧数据库表不视为运行时代码残留。

### 16.3 工程验收

1. 新业务逻辑有成功和失败路径测试。
2. 新接口有鉴权、越权、校验和幂等测试。
3. Agent 工具白名单测试通过。
4. Alembic 可从空数据库升级到最新版本。
5. 后端相关测试和全量 `pytest` 通过。
6. 前端 `npm run lint` 和 `npm run build` 通过。
7. 五分钟演示连续运行五次均成功。
8. 评测脚本可重复生成同格式报告。

## 17. 实施阶段

### 阶段一：新主流程骨架

- 新增 Farm Copilot Schema、上下文模块和接口；
- 新增主工作台；
- 调整默认路由和主导航；
- 保持旧闭环暂时可运行。

完成标准：

- 用户可以选择农场并看到今日上下文；
- 新旧功能没有共享可变前端状态。

### 阶段二：记录、建议和诊断

- 实现记录解析与确认；
- 实现建议结构化输出；
- 打通图片、天气、历史和知识库；
- 新增证据检查。

完成标准：

- 主演示故事可从头运行到设置提醒之前。

### 阶段三：提醒、周报和评委模式

- 新增 `FarmReminder` 和迁移；
- 实现提醒与周报；
- 迁移并简化运行时间线；
- 隐藏演示场景注入入口。

完成标准：

- 完整五分钟故事可运行；
- 普通用户界面不暴露旧闭环。

### 阶段四：删除旧闭环

- 删除旧前端组件、接口、业务模块、Skill、工具和运行分支；
- 清理 Schema 和注册表；
- 替换并新增测试；
- 使用全文扫描确认无运行时引用。

完成标准：

- 代码瘦身验收清单全部满足；
- 历史数据库升级和启动正常。

### 阶段五：评测与参赛材料

- 建立评测集；
- 运行三组基线；
- 固化演示数据；
- 重写五分钟视频剧本；
- 完成项目文档中的创新性、对比、指标和数据来源说明。

完成标准：

- 可生成评测报告；
- 视频在五分钟内；
- 演示连续五次成功；
- 参赛材料不包含学校、学院或导师身份信息。

## 18. 关键取舍

1. 删除的是旧运行链，不是已有农业数据能力。
2. 简单业务不强行使用 Agent，复杂咨询才使用多步骤规划。
3. 产品界面强调结果，Agent 轨迹只在评委模式展示。
4. 农事记录需要一次确认，但不演变成审批流。
5. 提醒使用简单模型，不复用旧复杂任务状态机。
6. 比赛前删除运行时代码，但不执行破坏性历史表清理。
7. 评测指标与五分钟演示和产品功能同等重要。
