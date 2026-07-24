# AgroAgentOS Farm Copilot 全量重构设计

**日期**：2026-07-24  
**状态**：待用户审阅  
**目标赛事**：第八届中国研究生人工智能创新大赛  
**产品定位**：面向家庭农场、合作社与农业服务组织的农业生产 Copilot

## 1. 重构决定

项目不再在原有“巡检、风险、提案、审批、任务、验收”的闭环上迭代。该闭环的领域语言属于作业调度系统，和比赛版的核心用户体验冲突。

新产品的唯一主流程是：

```text
文字、语音或照片
→ 识别用户意图
→ 加载所属农场的可信上下文
→ 解析记录或执行农业分析
→ 返回可编辑记录、带证据的建议或提醒
→ 用户确认需要持久化的结果
```

这次重构会替换：

- 运行时领域模型；
- Farm Copilot Agent 图；
- 业务接口；
- 用户端全部产品页面；
- 旧巡检、审批、任务和验收的服务、工具、Skill 与测试。

历史数据库迁移文件保留；旧表不自动删除。新运行时代码不依赖旧表。

## 2. 产品边界

### 2.1 核心用户任务

用户应能在同一工作台完成：

1. 查看今日最重要的地块事项；
2. 用一句话或语音记录农事；
3. 根据自己农场的天气、作物阶段和历史农事提问；
4. 上传作物图片进行上下文诊断；
5. 为建议设置复查提醒；
6. 查看本周生产记录、风险与投入摘要。

### 2.2 不做的能力

- 行动提案与人工审批；
- 工单分派、执行证据与 AI 验收；
- 多级组织、库存、采购、财务、追溯和供应链；
- 自动施药、自动灌溉或其他高风险设备控制；
- 面向用户的思维链和内部节点日志；
- 与农业生产无关的通用聊天、视频生成和市场行情主页面。

## 3. 新领域模型

新模型的领域语言是“生产事实”和“生产辅助”，不是“风险工单”。

```text
Farm
└── Plot
    └── CropCycle
        ├── FarmActivity
        ├── FieldObservation
        ├── FarmReminder
        └── CopilotRecommendation
```

### 3.1 `Farm`

保留所有权、名称、地点、面积和描述。已有 `farms` 表和所有权模型继续使用，不复制农场主数据。

### 3.2 `Plot`

替代运行时的 `Field`。一个地块属于一个农场，记录面积、土壤、边界、状态和说明。

新表：`plots`。

| 字段 | 说明 |
|---|---|
| `id` | 主键 |
| `farm_id` | 所属农场 |
| `name` | 地块名称，同农场唯一 |
| `area_mu` | 面积，亩 |
| `soil_type` | 土壤类型 |
| `boundary_json` | GeoJSON 边界 |
| `status` | `active/fallow/archived` |
| `note` | 备注 |

### 3.3 `CropCycle`

替代 `CropSeason` 作为地块当前和历史种植周期。每个周期只表达一茬作物，不维护与旧 `fields` 的双向指针。

新表：`crop_cycles`。

| 字段 | 说明 |
|---|---|
| `id` | 主键 |
| `plot_id` | 所属地块 |
| `crop_name` | 作物 |
| `variety` | 品种 |
| `started_on` | 播种或定植日期 |
| `expected_harvest_on` | 预计收获日期 |
| `growth_stage` | 当前生育期 |
| `status` | `planned/growing/harvested/aborted` |
| `area_mu` | 本茬面积 |
| `target_yield` | 目标产量文本 |
| `note` | 备注 |

同一 `plot_id` 在 `growing` 状态最多一条；这个约束在服务层和数据库唯一索引中同时保证。

### 3.4 `FarmActivity`

替代 `FarmEvent`。它是用户确认后的农事事实，不再携带旧任务弱关联。

新表：`farm_activities`。

| 字段 | 说明 |
|---|---|
| `id` | 主键 |
| `activity_id` | 对外 UUID |
| `farm_id` | 所属农场，便于查询 |
| `plot_id` | 所属地块 |
| `crop_cycle_id` | 可选种植周期 |
| `activity_type` | `seeding/fertilizing/irrigating/spraying/scouting/harvest/other` |
| `occurred_at` | 实际发生时间 |
| `operator_name` | 操作人 |
| `materials_json` | 类型化投入品列表 |
| `media_json` | 图片或附件引用 |
| `note` | 用户备注 |
| `source` | `manual/copilot/import` |
| `client_request_id` | 幂等键 |

`client_request_id` 与 `farm_id` 联合唯一。输入不完整时只生成 `ActivityDraft`，不能写入本表。

### 3.5 `FieldObservation`

替代 `SensorReading`。观测既可以来自传感器，也可以来自照片、人工巡田和比赛 fixture。

新表：`field_observations`。

| 字段 | 说明 |
|---|---|
| `id` | 主键 |
| `observation_id` | 对外 UUID |
| `farm_id` | 所属农场 |
| `plot_id` | 所属地块 |
| `crop_cycle_id` | 可选种植周期 |
| `kind` | `soil_moisture/pest_count/vegetation_index/image_symptom/manual_note/other` |
| `value_number` | 数值观测，可空 |
| `unit` | 数值单位 |
| `payload_json` | 类型化补充载荷 |
| `observed_at` | 观测时间 |
| `source` | `sensor/image/manual/fixture` |
| `media_json` | 图片引用 |

### 3.6 `FarmReminder`

提醒是简单待办，不复用旧 `FarmTask`。

新表：`farm_reminders`。

| 字段 | 说明 |
|---|---|
| `id` | 主键 |
| `reminder_id` | 对外 UUID |
| `farm_id` | 所属农场 |
| `plot_id` | 可选地块 |
| `title` | 提醒标题 |
| `note` | 提醒说明 |
| `due_at` | 到期时间 |
| `status` | `pending/done/cancelled` |
| `source` | `manual/advice/brief` |
| `source_run_id` | 可选 Copilot 运行引用 |

允许的状态转换只有 `pending → done` 与 `pending → cancelled`。

### 3.7 `CopilotRecommendation`

持久化用户实际看到的建议，作为后续追问和比赛证据的事实来源。

新表：`copilot_recommendations`。

| 字段 | 说明 |
|---|---|
| `id` | 主键 |
| `recommendation_id` | 对外 UUID |
| `run_id` | 对应 Copilot 运行 |
| `farm_id` | 所属农场 |
| `plot_id` | 可选地块 |
| `kind` | `daily_brief/advice/diagnosis` |
| `title` | 标题 |
| `summary` | 建议结论 |
| `confidence` | 0 到 1 |
| `evidence_json` | 实测、规则、知识和推断的类型化列表 |
| `actions_json` | 建议动作 |
| `data_gaps_json` | 数据缺口 |
| `created_at` | 创建时间 |

它不含批准、拒绝和执行状态。用户可以从建议创建提醒，但建议本身不是工单。

### 3.8 迁移原则

新迁移 `012_create_farm_copilot_schema.py`：

1. 创建五张新表和必要索引；
2. 从 `fields` 复制地块事实到 `plots`；
3. 从 `crop_seasons` 复制种植周期到 `crop_cycles`；
4. 从 `farm_events` 复制用户农事事实到 `farm_activities`；
5. 从 `sensor_readings` 复制观测到 `field_observations`；
6. 不复制旧提案和任务；
7. 不删除任何旧表；
8. 新代码只读写新表。

迁移需同时支持 SQLite 和 MySQL。迁移前后都必须保留旧表，降级只删除新表，不修改旧表。

## 4. Farm Copilot Agent 图

```text
START
  ↓
RequestClassifier
  ↓
FarmContextLoader
  ├─ record_activity ──→ ActivityExtractor ──→ DraftValidator ───┐
  ├─ get_daily_brief ──→ BriefBuilder ────────────────────────────┤
  ├─ get_weekly_report → ReportBuilder ───────────────────────────┤
  ├─ create_reminder ──→ ReminderDraftBuilder ────────────────────┤
  └─ ask_advice / diagnose_image
       ↓
     SkillRouter → Planner → Executor → EvidenceGuard → Replanner
       ↓
     RecommendationPresenter ─────────────────────────────────────┘
  ↓
ResultPresenter
  ↓
END
```

### 4.1 图规则

- `RequestClassifier` 只返回固定意图和置信度；不调用工具。
- `FarmContextLoader` 只读取当前认证用户拥有的农场数据。
- 记录、简报、报告和提醒路径不进入 Planner/Replanner。
- 复杂建议路径保留 `SkillRouter → Planner → Executor → Replanner` 的职责关系，满足现有运行时约束。
- `EvidenceGuard` 是新节点：标注实测、规则、知识、推断和数据缺口；不允许无依据的确定性结论。
- `ResultPresenter` 只组装类型化结果，不保存农事活动或提醒。
- `FarmActivity` 与 `FarmReminder` 的写入通过用户确认接口完成，Agent 没有直接写工具。

### 4.2 新 Skill

只保留两个复杂 Skill：

- `farm_advice`：天气、知识库、观测和农事历史的综合建议；
- `crop_diagnosis`：图片、观测、作物阶段和历史农事的联合诊断。

两个 Skill 均只允许只读工具。工具失败、超步数或证据不足时，Replanner 必须收敛到带数据缺口的结果。

## 5. 后端模块

新模块按业务概念组织：

```text
app/models/production.py              # Plot、CropCycle、FarmActivity、FieldObservation
app/models/copilot.py                 # FarmReminder、CopilotRecommendation
app/schemas/production.py             # 领域输入和输出类型
app/schemas/farm_copilot.py           # 交互、SSE、建议和简报类型
app/services/production_context_service.py
app/services/farm_activity_service.py
app/services/field_observation_service.py
app/services/farm_reminder_service.py
app/services/farm_brief_service.py
app/services/farm_report_service.py
app/services/farm_copilot_service.py
app/agents/farm_copilot_graph.py
app/agents/farm_copilot_nodes.py
app/tools/farm_copilot_tools.py
app/api/v1/farm_copilot.py
```

路由只处理请求、认证和 SSE 包装；所有数据库查询和状态转换在服务模块内完成。

## 6. API

新接口统一位于 `/api/v1/farm-copilot`：

```text
GET  /today?farm_id=&plot_id=
POST /interactions/stream
POST /activities/parse
POST /activities
GET  /activities?farm_id=&plot_id=&days=
POST /reminders
GET  /reminders?farm_id=&status=
POST /reminders/{reminder_id}/complete
POST /reminders/{reminder_id}/cancel
GET  /reports/weekly?farm_id=&week=
GET  /runs/{run_id}/timeline
```

`/activities/parse` 生成可编辑草稿；`/activities` 只接受用户确认的类型化数据和 `client_request_id`。

`/interactions/stream` 的公开 SSE 事件固定为：

```text
start
context_loaded
analyzing
source_found
result
complete
error
```

内部图节点、工具参数和模型思维过程只保存于运行记录，评委模式才读取摘要。

## 7. 全部用户页面

用户端路由收敛为：

```text
/                              → FarmCopilotPage
/workspace/farm               → FarmProfilePage
/workspace/records            → FarmRecordsPage
/workspace/reports            → FarmReportsPage
/profile                       → ProfilePage
/login                         → LoginPage
```

管理员页面保留 `/workspace/users`，但不属于比赛视频。

### 7.1 `FarmCopilotPage`

默认页面。显示农场选择、地块上下文、今日三项关注、统一输入、建议卡、提醒和最近农事。

### 7.2 `FarmProfilePage`

统一管理农场、地块和种植周期。地图仅作为地块边界编辑和查看，不再和风险工单绑定。

### 7.3 `FarmRecordsPage`

按地块、作物周期和时间查看 `FarmActivity` 与 `FieldObservation`。支持手工补录和编辑自己创建的活动。

### 7.4 `FarmReportsPage`

显示周报、投入品汇总、已完成提醒、数据缺口和建议趋势。比赛版不做财务报表。

### 7.5 删除的用户页面

删除：

```text
Chat.tsx
Dashboard.tsx
Weather.tsx
PestDiagnosis.tsx
MarketPrice.tsx
Knowledge.tsx
VideoGen.tsx
AgentCapabilities.tsx
FarmAgent.tsx
```

对应独立 UI API、类型、状态和组件一并删除；可复用的图片上传、地图、认证和通用 UI 模块迁移后保留。

## 8. 删除旧运行链

新产品通过端到端测试后删除：

```text
app/models/farm_agent.py
app/api/v1/farm_agent.py
app/api/v1/farm_tasks.py
app/services/farm_agent_service.py
app/services/farm_proposal_service.py
app/services/farm_task_service.py
app/services/farm_risk_service.py
app/services/farm_snapshot_service.py
app/services/farm_run_query_service.py
app/services/farm_query_service.py
app/tools/farm_agent_tools.py
app/skills/definitions/farm_inspection/
app/skills/definitions/farm_task_verification/
frontend-react/src/components/farm-agent/
frontend-react/src/api/farmAgent.ts
frontend-react/src/api/farmTasks.ts
frontend-react/src/stores/farmAgent.ts
frontend-react/src/types/farmAgent.ts
```

删除旧测试时，必须以新领域模型、接口和图的测试替换；额外保留旧路由返回 404 的迁移测试。

## 9. 失败与安全规则

- 未选择农场或地块时，系统只请求缺少的一个上下文，不猜测归属。
- 天气或知识库不可用时，返回明确的缺口并降低置信度。
- 图片质量差时要求重拍，不能给出伪确定诊断。
- LLM 不可用时，活动原文和确定性简报仍可用，不能伪造解析成功。
- 涉及药剂、剂量和安全间隔期时，必须引用可靠知识；否则只给人工复查建议。
- 所有新写入接口使用幂等键和农场归属校验。

## 10. 验收标准

1. 新运行时代码不导入或查询旧 `Field`、`CropSeason`、`FarmEvent`、`SensorReading`、`FarmActionProposal` 或 `FarmTask` 模型。
2. `FarmCopilotPage` 是认证后的默认页面，旧页面及路由不存在。
3. 用户能够完成“今日简报、记录草稿确认、上下文图片诊断、创建提醒、查看周报”完整流程。
4. 复杂建议经过 EvidenceGuard，输出证据、置信度和数据缺口。
5. 新 Agent 图覆盖六种固定意图，并为复杂意图保留 Planner/Executor/Replanner。
6. 新迁移可从空数据库升级，且不删除旧表。
7. 新后端和迁移测试、全量 `pytest`、前端 `npm run lint`、`npm run build` 全部通过。
8. 比赛演示五分钟内可连续完成五次。

## 11. 分阶段交付

### 阶段 A：领域核心

创建新表、迁移旧生产事实、实现 Production Context、活动与提醒服务，并通过单元和迁移测试。

### 阶段 B：新图与接口

实现 Farm Copilot Graph、复杂 Skill、证据检查、结构化交互 SSE 和新 API。

### 阶段 C：全量页面

实现四个新页面和统一导航，复用认证、上传、地图和 UI 基础模块。

### 阶段 D：删除旧链

删除旧模型、服务、接口、工具、Skill、页面和测试；添加 404 迁移测试与全仓库残留扫描。

### 阶段 E：评测与比赛

创建记录提取、建议依据、风险场景和图片诊断评测集；运行基线对比；固化五分钟演示。
