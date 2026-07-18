# AgroAgentOS 比赛版农场闭环智能体设计

**日期**：2026-07-18  
**状态**：已完成方案讨论，待用户审阅书面设计  
**目标版本**：人工智能大赛演示版

## 1. 背景与目标

AgroAgentOS 已具备农场与地块管理、天气风险规则、农业知识库 RAG、病虫害识别、农机轨迹分析，以及 `SkillRouter → Planner → Executor → Replanner` 的 LangGraph 执行链路。但这些能力目前分散在独立页面和两条不同运行路径中：普通 Chat 能读取用户农场上下文，却主要表现为问答；LangGraph 能展示多步骤规划和工具调用，却仍沿用 AIOps 接口和部分 SRE 文案，也没有绑定已认证用户的农场上下文。

比赛版不建设完整农场 SaaS，而是将现有能力连接为一条可演示、可审计、有人类确认的智能体闭环：

```text
读取真实农场数据
→ 多智能体联合巡检
→ 生成有证据的风险判断
→ 创建待确认行动方案
→ 人工批准生成任务
→ 提交执行证据
→ AI 复核并在必要时重新规划
```

产品定位为：

> AgroAgentOS：面向农场生产的多智能体自主决策与协同执行系统。

## 2. 范围

### 2.1 一期范围

一期实现以下完整故事：

1. 用户选择自己拥有的农场并启动 AI 综合巡检。
2. 智能体读取农场、地块、作物、生长阶段、近期轨迹和已有任务。
3. 智能体调用天气、知识库和轨迹分析能力收集证据。
4. 智能体生成结构化风险项与行动方案草稿。
5. 用户批准、修改或拒绝方案；只有批准后才生成正式任务。
6. 执行人员提交文字、轨迹等执行证据。
7. 智能体对照任务目标复核执行质量，输出通过、补充证据或返工建议。
8. 人工确认任务完成或退回。

主演示场景为“暴雨来临前的智能农场巡检”。

### 2.2 明确不做

一期不实现：

- 自定义角色与细粒度权限后台；
- 财务、库存、采购和人员绩效；
- 合作社多级组织架构；
- 多级审批流；
- 全功能离线小程序；
- 通用照片验收；
- Agent 自动执行施药、删除、任务完成等高风险写操作。

现有平台级 `admin/user` 角色保持不变。比赛演示中的农场主、生产管理员和作业人员是业务视角，不在一期扩展为完整 RBAC 系统。

一期所有有副作用的操作仍由农场所有者的已认证账号完成。“作业人员”以任务卡片中的执行人名称和演示视角体现，不提供独立作业人员登录，也不因此授予其他用户访问该农场的权限。若赛后需要真实多人登录，再单独设计 `FarmMembership` 和农场级 RBAC。

## 3. 方案选择

评估过三种路径：

1. **只增强 Chat**：改动最少，但仍像 RAG 问答机器人。
2. **直接改写 AIOps 接口**：可以复用 LangGraph，但会继续混合诊断、业务和历史兼容逻辑。
3. **复用运行时，新增 Farm Agent 应用层**：保留现有接口兼容，提取通用 SSE 执行能力，新增农场业务模型、工具、Skill 和前端驾驶舱。

采用第三种。该方案不重写 LangGraph，也不复制整套执行流。

## 4. 总体架构

```text
React AI 农场驾驶舱
        │ SSE / REST
        ▼
FarmAgent API / FarmTask API
        ▼
FarmAgentService
        ├─ 校验当前用户与农场归属
        ├─ 设置 FarmRunContext
        └─ 调用通用 AgentStreamService
                    ▼
           LangGraph Agent Runtime
    SkillRouter → Planner → Executor → Replanner
                    │
                    ├─ 农场数据分析 Agent
                    ├─ 农技研究 Agent
                    └─ 农事规划 Agent
                    │
                    ▼
        农场工具 / 天气工具 / RAG / 轨迹工具
                    ▼
       FarmActionProposal / FarmTask / AgentRun
```

### 4.1 分层规则

- `app/api/v1/` 只做参数、认证、依赖注入、SSE 包装和响应组装。
- `app/services/` 负责快照聚合、风险规则、方案状态和任务状态转换。
- `app/tools/` 是 Agent 对服务层的受控适配器，不直接堆放数据库业务逻辑。
- `app/agents/` 保持路由、规划、执行和重规划边界。
- ORM 变更通过新 Alembic 迁移完成，并兼容 SQLite 与 MySQL。

## 5. 核心领域模型

### 5.1 FarmActionProposal

Agent 只能创建待确认提案，不能直接创建高风险正式任务。

| 字段 | 含义 |
|---|---|
| `id` | 数据库主键 |
| `proposal_id` | 对外 UUID，唯一 |
| `farm_id` | 所属农场 |
| `created_by` | 发起巡检的用户 |
| `run_id` | 关联 AgentRun |
| `title` | 提案标题 |
| `severity` | `low/medium/high/critical` |
| `summary` | 风险概述 |
| `evidence_json` | 结构化证据列表 |
| `actions_json` | 结构化建议动作列表 |
| `status` | `pending/approved/rejected` |
| `decision_note` | 人工修改或拒绝原因 |
| `created_at` | 创建时间 |
| `decided_at` | 决策时间 |

`evidence_json` 中每条证据至少包含来源类型、来源标识、摘要和观测时间。资料不足时必须明确标记为推断，不能伪装成实测数据。

### 5.2 FarmTask

| 字段 | 含义 |
|---|---|
| `id` | 数据库主键 |
| `task_id` | 对外 UUID，唯一 |
| `proposal_id` | 来源提案，可为空 |
| `farm_id` | 所属农场 |
| `field_id` | 目标地块，可为空 |
| `assignee_name` | 执行人显示名称，可为空；不参与鉴权 |
| `title` | 任务标题 |
| `task_type` | 排水、巡田、喷药、复查等 |
| `instructions` | 可执行要求 |
| `priority` | `normal/high/urgent` |
| `status` | 任务状态 |
| `due_at` | 截止时间 |
| `execution_json` | 实际执行数据与证据 |
| `agent_verdict_json` | AI 复核草稿 |
| `created_at` | 创建时间 |
| `updated_at` | 更新时间 |

任务状态机固定为：

```text
pending → in_progress → submitted → completed
                          └──────→ returned → in_progress
pending / in_progress → cancelled
```

禁止从 `pending` 直接跳转到 `completed`。AI 只能写入复核草稿，最终完成和退回由普通业务 API 执行。

### 5.3 AgentRun 扩展

在现有 `agent_runs` 上增加可空字段：

- `user_id`
- `farm_id`
- `run_type`：`inspection/task_verification`
- `context_snapshot_json`
- `outcome_json`

保留现有步骤数、工具调用数、Token、耗时、模型和 transition history，用于比赛现场展示可观测性。

## 6. 安全运行上下文

新增 `app/runtime/farm_run_context.py`，通过 `ContextVar` 保存经过 API 鉴权和农场归属校验的：

```python
FarmRunContext(
    user_id=current_user.id,
    farm_id=validated_farm_id,
    run_id=run_id,
)
```

Agent 工具不得接收由模型自由填写的 `user_id`。工具从运行上下文读取身份，并在服务层再次确认目标农场、地块、轨迹和任务属于当前用户范围。异步图执行任务会继承 ContextVar；单元测试必须覆盖上下文缺失、跨用户访问和并发隔离。

## 7. Agent 状态与运行时

`PlanExecuteState` 增加：

```text
user_id
farm_id
run_id
run_type
business_context
proposal_ids
```

现有 `selected_skill`、`plan`、`past_steps`、`iteration`、`tried_skills`、`transition_history` 和权限模式继续使用。

新增通用 `AgentStreamService`，从现有 `aiops_service` 提取以下能力：

- 图执行与取消；
- stream sink 合并；
- 节点事件转 SSE；
- Token、工具调用和耗时统计；
- transition history；
- AgentRun 持久化；
- 并发限制与预算事件。

`aiops_service.py` 保留为兼容包装；Farm Agent 传入业务初始状态和农业事件文案。`build_aiops_graph()` 增加通用别名 `build_agent_graph()`，旧调用继续可用。

## 8. 农业工具

新增 `app/tools/farm_agent_tools.py`。

### 8.1 只读工具

1. `get_farm_snapshot`
   - 返回农场、地块、作物、生长阶段、面积、位置和更新时间。
2. `inspect_farm_weather_risks`
   - 获取未来预报，复用现有确定性天气风险规则，返回阈值、预报值和建议。
3. `get_field_work_quality`
   - 返回近期轨迹作业面积、耕深、深度波动、达标率和效率。
4. `get_pending_farm_tasks`
   - 检查同农场、同地块和同风险类型的未完成任务，避免重复建议。
5. `get_task_evidence`
   - 返回任务目标、执行说明、关联轨迹和可用附件信息。

### 8.2 受控写工具

1. `create_action_proposal`
   - 只创建 `pending` 提案；参数由 Pydantic 校验；使用 `run_id + 风险指纹` 保证幂等。
2. `save_task_verification_draft`
   - 只写入 `agent_verdict_json`，不能改变任务最终状态。

查询工具登记为低风险只读工具。写草稿工具登记为中风险、非并发、数据库副作用工具。批准、拒绝、完成、退回和删除不暴露为 Agent 工具。

## 9. Skill 与二级 Agent

### 9.1 farm_inspection

执行顺序：

1. 获取农场快照。
2. 检查天气风险。
3. 检查近期轨迹和待办。
4. 对高风险项检索知识库。
5. 区分实测证据、规则判断和模型推断。
6. 创建结构化行动提案草稿。
7. 输出农业风险报告和待人工确认事项。

### 9.2 farm_task_verification

执行顺序：

1. 获取任务目标和验收条件。
2. 获取执行证据和轨迹质量。
3. 对比计划与实际。
4. 输出 `pass/needs_evidence/rework/manual_review` 建议。
5. 保存复核草稿，等待人工决定。

### 9.3 二级 Agent

- **农场数据分析 Agent**：只收集农场、地块、轨迹和任务事实，不给处置建议。
- **农技研究 Agent**：负责天气、知识库、作物阶段和病虫害诱发条件，资料不足时标记不确定性。
- **农事规划 Agent**：基于已有证据制定优先级、动作、截止时间和验收条件，不自行调用高风险写操作。

主 Executor 负责协调二级 Agent，并由受控工具保存最终草稿。

## 10. 提示词一致性

现有运行链中残留 SRE、故障诊断和服务器根因分析文案。比赛版需要将 Farm Agent 报告统一为：

- 农业风险分析报告；
- 关键证据；
- 风险等级；
- 行动方案；
- 不确定性与待确认项；
- 复查时间。

兼容 AIOps 路由可以保留旧事件名称，但 Farm Agent 不得输出“服务器故障”“SRE 根因”等无关文案。最终测试对此做明确断言。

## 11. API

### 11.1 智能巡检

```http
POST /api/v1/farm-agent/inspections/stream
```

请求包含 `farm_id`、可选自然语言目标和可选演示场景标识。接口必须使用 `get_current_user`，并在启动图之前校验农场归属。

SSE 事件包括：

```text
start
context_loaded
skill_selected
plan
step_start
tool_call
step_complete
replan
proposal_created
report
complete
error
```

### 11.2 提案

```http
GET  /api/v1/farm-agent/proposals
POST /api/v1/farm-agent/proposals/{proposal_id}/approve
POST /api/v1/farm-agent/proposals/{proposal_id}/reject
```

批准请求允许用户删除动作或调整负责人、截止时间和说明。批准必须幂等，同一提案只能生成一组任务。

### 11.3 任务

```http
GET  /api/v1/farm-tasks
POST /api/v1/farm-tasks/{task_id}/start
POST /api/v1/farm-tasks/{task_id}/submit
POST /api/v1/farm-tasks/{task_id}/verify/stream
POST /api/v1/farm-tasks/{task_id}/complete
POST /api/v1/farm-tasks/{task_id}/return
```

路由不直接操作数据库，所有状态转换由 `farm_task_service` 校验。

## 12. 前端体验

新增 `/workspace/farm-agent` AI 农场驾驶舱。

### 12.1 页面布局

- 顶部：农场选择、真实/演示数据标识、开始 AI 巡检按钮。
- 左侧：农场地图、地块和风险等级。
- 中间：实时 Agent 计划、工具调用、步骤完成和重规划时间线。
- 右侧：待确认行动提案及证据。
- 底部：待执行、执行中、待复核和已完成任务看板。

### 12.2 组件边界

- `AgentRunTimeline`：只负责 SSE 事件展示，复用现有 ProgressSteps 数据转换思想。
- `FarmRiskCard`：展示风险、地块和证据来源。
- `ActionProposalCard`：展示结构化建议和人工修改入口。
- `HumanApprovalBar`：负责批准、修改和拒绝。
- `FarmTaskBoard`：按状态展示任务。
- `TaskVerificationCard`：展示 AI 复核建议和人工决定。

React Query 管理提案与任务等服务端状态；SSE 实时状态由页面 hook 或独立 Zustand slice 管理；所有 API 集中在 `frontend-react/src/api/`，共享类型放在 `frontend-react/src/types/`。

### 12.3 工作台调整

现有工作台的系统健康卡片降为次要区域。首屏突出：

- 今日 AI 风险摘要；
- 待确认提案数量；
- 进行中任务；
- 最近一次巡检结果；
- “开始 AI 综合巡检”主操作。

现有农场 CRUD 与轨迹页面不重做，仅增加跳转到 AI 巡检的入口。

## 13. 演示数据与可复现性

新增显式标识的比赛演示场景，避免现场网络导致演示失败：

- 阳光农场和三个地块；
- A1 水稻处于分蘖期；
- 未来 24 小时降水 82mm；
- 一条质量偏低的农机轨迹；
- 一个尚未处理的风险项。

演示场景只提供输入数据，不写死 Agent 计划和报告。界面必须显示“当前使用比赛演示数据”。正常模式仍调用真实天气与数据库数据。

演示数据通过专用 seed 脚本和版本化 JSON fixture 提供，不在业务服务中硬编码。

## 14. 异常与降级

- **没有农场**：终止巡检并给出创建农场或加载演示数据入口。
- **天气不可用**：标记降级巡检，不创建高置信度气象任务。
- **Milvus 不可用**：保留规则分析，但标记知识证据缺失。
- **LLM 参数错误**：Pydantic 拒绝工具调用，Replanner 在步数上限内修正。
- **重复巡检**：按运行 ID 和风险指纹抑制重复提案。
- **重复批准**：返回同一批任务，不能重复插入。
- **客户端断开**：取消图任务；已完成的草稿写入保留。
- **越权访问**：统一返回 403，不泄露资源是否存在。
- **高风险农业建议**：施药等内容必须显示安全间隔期、证据和人工确认提示。
- **无法收敛**：输出已收集证据和“需要人工介入”，不能伪造成功。

## 15. 测试与验收

### 15.1 后端测试

必须覆盖：

- 农场快照仅包含当前用户数据；
- ContextVar 并发隔离和缺失上下文失败；
- 暴雨输入触发确定性风险；
- 天气和知识库失败时正确降级；
- 没有有效证据时不能生成高置信度提案；
- Agent 只能创建草稿；
- 提案批准幂等；
- 非法任务状态转换被拒绝；
- 任务复核不能直接完成任务；
- Skill 工具白名单和 ToolMeta 完整；
- Replanner 超步数时收敛；
- Farm Agent 最终报告不包含 SRE 或服务器故障文案；
- SSE 在成功、工具失败、图失败和客户端取消时均正确结束。

### 15.2 前端验证

项目暂未配置前端测试框架，一期不为此单独引入依赖。必须运行：

```bash
npm run lint
npm run build
```

并手工验证加载、空数据、错误、成功、重复点击和 SSE 中断状态。

### 15.3 完整冒烟流程

```text
加载演示农场
→ 启动巡检
→ 查看 Agent 时间线和证据
→ 生成待审批提案
→ 批准生成任务
→ 启动并提交任务证据
→ AI 复核
→ 人工完成或退回
```

### 15.4 完成标准

一期完成必须同时满足：

1. 演示场景无需手动编辑数据库即可初始化。
2. 巡检过程中至少出现农场、天气、知识和轨迹四类证据中的三类。
3. 前端可见 Skill 选择、计划、工具调用、重规划或完成状态。
4. 提案是结构化数据，不依赖从 Markdown 反向解析。
5. 未经人工批准不会生成正式任务。
6. AI 复核不会直接修改任务最终状态。
7. 真实模式和演示模式有清晰标识。
8. Alembic 升级、相关 pytest、全量 pytest、前端 lint 和 build 均通过，或如实记录无法通过的原因。

## 16. 预计代码变更

### 16.1 新增后端文件

```text
app/api/v1/farm_agent.py
app/api/v1/farm_tasks.py
app/models/farm_agent.py
app/schemas/farm_agent.py
app/services/agent_stream_service.py
app/services/farm_agent_service.py
app/services/farm_snapshot_service.py
app/services/farm_risk_service.py
app/services/farm_proposal_service.py
app/services/farm_task_service.py
app/runtime/farm_run_context.py
app/tools/farm_agent_tools.py
app/skills/definitions/farm_inspection/SKILL.md
app/skills/definitions/farm_task_verification/SKILL.md
alembic/versions/007_add_farm_agent_workflow.py
scripts/seed_competition_demo.py
app/data/demo_rainstorm_scenario.json
```

### 16.2 修改后端文件

```text
app/main.py
app/models/__init__.py
app/agents/state.py
app/agents/graph.py
app/agents/skill_router.py
app/agents/subagents/__init__.py
app/agents/replanner.py
app/runtime/agent_harness.py
app/tools/mcp_loader.py
app/tools/meta.py
app/services/aiops_service.py
app/core/sqlite.py
app/config.py
.env.example
```

只有在新增演示模式配置时才修改 `app/config.py` 和 `.env.example`。不增加新第三方依赖。

### 16.3 新增前端文件

```text
frontend-react/src/pages/FarmAgent.tsx
frontend-react/src/api/farmAgent.ts
frontend-react/src/api/farmTasks.ts
frontend-react/src/types/farmAgent.ts
frontend-react/src/components/farm-agent/AgentRunTimeline.tsx
frontend-react/src/components/farm-agent/FarmRiskCard.tsx
frontend-react/src/components/farm-agent/ActionProposalCard.tsx
frontend-react/src/components/farm-agent/HumanApprovalBar.tsx
frontend-react/src/components/farm-agent/FarmTaskBoard.tsx
frontend-react/src/components/farm-agent/TaskVerificationCard.tsx
```

### 16.4 修改前端文件

```text
frontend-react/src/App.tsx
frontend-react/src/pages/Dashboard.tsx
frontend-react/src/pages/Farms.tsx
frontend-react/src/components/layout/AppLayout.tsx
```

对 `Farms.tsx` 只增加巡检入口，不重构现有大型页面。

## 17. 实施阶段

1. 建立提案、任务和 AgentRun 数据结构，完成迁移与服务层测试。
2. 建立安全 FarmRunContext、农场快照和确定性风险工具。
3. 新增 Farm Skill、农业二级 Agent 和提示词一致性修正。
4. 提取通用 SSE 执行服务，提供巡检与提案 API。
5. 实现任务状态机、执行证据和 AI 复核。
6. 实现 AI 农场驾驶舱和工作台入口。
7. 增加演示 seed、异常兜底、集成冒烟与全量验证。

预计完整一期为 9–13 个有效开发日。若比赛时间紧张，可先交付“巡检 → 提案 → 人工批准 → 任务”作为内部阶段性演示，把 AI 复核放到下一批；该 6–8 个有效开发日的阶段版本不满足本设计第 15.4 节定义的完整一期完成标准。

## 18. 主要风险与控制

| 风险 | 控制措施 |
|---|---|
| 作品仍像聊天机器人 | 主入口改为 AI 巡检，展示计划、工具、证据和行动方案 |
| LLM 编造风险数据 | 风险阈值由代码计算，报告区分实测、规则和推断 |
| Agent 越权写业务数据 | 使用 ContextVar、服务层鉴权和只写草稿工具 |
| 现场网络不稳定 | 提供明确标识的演示输入 fixture |
| 范围失控 | 不做库存、财务、组织和完整权限系统 |
| 照片验收能力被夸大 | 一期只把照片作为人工证据；YOLO 仅用于病虫害识别 |
| 旧 AIOps 文案污染 | Farm Agent 使用农业事件配置，并增加回归断言 |
| SSE 重构引入回归 | 保留兼容包装，分别测试旧入口和 Farm Agent 入口 |

## 19. 最终决策

比赛版采用“复用现有 LangGraph 运行时，新增 Farm Agent 应用层”的方案。一期核心闭环固定为：

> AI 农场巡检 → 有证据的行动提案 → 人工批准 → 任务执行 → AI 轨迹复核。

该边界能够集中展示 AgroAgentOS 的智能体价值，同时避免将时间消耗在完整农场管理网站建设上。
