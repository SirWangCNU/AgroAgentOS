# AgroAgentOS 架构说明 — 农场管理 × AI 驾驶舱联动

> 本文档说明 AgroAgentOS 在比赛演示场景下的整体架构、核心设计决策与验证策略
> 适用版本：Week 1-4 完整实施后
> 配套文档：[演示剧本](./competition-demo-script.md)、[开发规范](./DEVELOPMENT_STANDARDS.md)

---

## 一、项目背景与目标

### 1.1 问题域

农业生产决策长期依赖经验，缺乏数据驱动的闭环支撑。现有农业平台或偏重 IoT 数据采集（如大疆农业），或偏重经营管理（如 JD Operations Center），鲜有把"感知-认知-决策-执行-反馈"做成完整闭环的产品。

### 1.2 项目目标

AgroAgentOS 旨在用多 agent 架构打通农业生产的闭环：

1. **感知层**：通过传感器读数（土壤含水量、虫情、NDVI 等）和气象数据采集农场状态
2. **认知层**：基于确定性规则 + LLM 推理生成风险判断，每条风险带完整证据链
3. **决策层**：AI 起草结构化行动提案，人工审批后转为可执行任务
4. **执行层**：作业人员执行任务并提交证据，AI 复核 + 人工确认完成
5. **反馈层**：任务完成自动写事件，形成不可变记忆，影响下一轮认知

### 1.3 比赛演示约束

- **无硬件设备**：通过 fixture 文件模拟田间传感器读数
- **可复现性**：风险判定不依赖 LLM 随机性，用确定性阈值保证现场可复现
- **时间窗口**：3-4 周完成从数据底座到前端联动的全栈实现
- **演示形态**：先引导演示 10 步剧本，后开放自由探索

---

## 二、整体架构

### 2.1 技术栈

| 层 | 技术选型 | 说明 |
|----|----------|------|
| 前端 | React 19 + Vite + TypeScript | Zustand 状态管理，TanStack Query 服务端状态，Tailwind CSS 样式 |
| 后端 | Python 3.11 + FastAPI | Pydantic Settings 配置，SQLAlchemy ORM，Alembic 迁移 |
| Agent | LangGraph | `SkillRouter → Planner → Executor → Replanner` 图 |
| 数据库 | SQLite（开发）/ MySQL（生产） | 通过 `USE_SQLITE` 切换 |
| 向量库 | Milvus | RAG 混合检索（BM25 + 向量 + RRF） |
| 缓存 | Redis | 会话与中间态 |
| LLM | DashScope → DeepSeek → Ollama | 三级 fallback |

### 2.2 架构分层

```
┌─────────────────────────────────────────────────────────┐
│  Frontend (React 19 + Vite)                             │
│  ├─ pages/        FarmAgent / Farms / Dashboard         │
│  ├─ components/   farm-agent/* (RiskCard, SensorPanel…) │
│  ├─ stores/       Zustand (auth/conversation/health/ui) │
│  └─ api/          authFetch + consumeSSE                │
└────────────────────────┬────────────────────────────────┘
                         │ HTTP + SSE
┌────────────────────────▼────────────────────────────────┐
│  Backend (FastAPI)                                       │
│  ├─ api/v1/       16 routers (under /api/v1)            │
│  ├─ services/     business logic (no DB calls in router)│
│  ├─ agents/       LangGraph (SkillRouter→Planner→…)     │
│  ├─ core/         database / milvus / redis / llm / mcp │
│  ├─ models/       SQLAlchemy ORM                        │
│  ├─ schemas/      Pydantic request/response             │
│  └─ skills/       YAML playbook + Markdown              │
└────────────────────────┬────────────────────────────────┘
                         │
        ┌────────────────┼────────────────┐
        ▼                ▼                ▼
   SQLite/MySQL       Milvus           Redis
   (业务数据)        (向量检索)        (缓存)
```

### 2.3 请求流转

以"启动 AI 综合巡检"为例：

1. 前端 `POST /api/v1/farm-agent/inspection`，带 `farm_id` 和 `demo_scenario`
2. `farm_agent_service.stream_inspection` 先调用 `demo_scenario_service.inject_scenario_to_db` 注入感知数据
3. 调用 `farm_snapshot_service.build_snapshot` 聚合农场快照（fields + sensor_readings + recent_events）
4. 启动 LangGraph，`Executor` 节点调用 `farm_inspect` 工具
5. `farm_risk_service.inspect_farm` 基于确定性规则生成风险列表
6. `planner` 节点调用 LLM 把风险转为结构化提案（`ProposalDraft`）
7. 提案持久化，SSE 推送 `proposal_created` 事件
8. 前端流式接收，渲染风险卡片与提案列表

---

## 三、农场管理 × AI 驾驶舱联动设计

### 3.1 三表事实底座

联动的基础是三张事实表，把农场运营的"作物生命周期"和"作业事件"结构化：

| 表 | ORM 模型 | 作用 |
|----|----------|------|
| `crop_seasons` | `CropSeason` | 记录每个地块每个茬次的作物、品种、生育期、目标产量 |
| `sensor_readings` | `SensorReading` | 记录感知读数（土壤含水量、虫情、NDVI 等），带 `scenario_id` 标识来源 |
| `farm_events` | `FarmEvent` | 不可变事件流，记录所有作业（喷药、施肥、灌溉、排水等） |

这三张表通过 `field_id` 关联，构成农场运营的完整事实链。

### 3.2 事件流闭环

```
感知注入                    认知                    决策                执行              反馈
   │                         │                      │                  │                 │
   ▼                         ▼                      ▼                  ▼                 ▼
SensorReading         farm_risk_service        Proposal           FarmTask           FarmEvent
   │                         │                      │                  │                 │
   │         build_snapshot  │                      │                  │                 │
   └─────────────────────────┘                      │                  │                 │
        ▲                                           │                  │                 │
        │                                           ▼                  │                 │
        │                                      approve/reject           │                 │
        │                                           │                  ▼                 │
        │                                           │           start/submit/complete    │
        │                                           │                  │                 │
        │                                           │                  └────────────────▶│
        │                                           │                                    │
        └───────────────────────────────────────────────────────────────────────────────────┘
                              下一轮 snapshot 携带 recent_events
```

关键设计：`farm_task_service.complete()` 在任务完成时自动插入一条 `FarmEvent`，记录作业类型、投入品、操作人、关联任务 ID。这条事件会被下一轮 `build_snapshot` 的 `recent_events` 字段携带，让 Agent 拥有"记忆"。

### 3.3 前端联动

| 页面 | 联动组件 | 数据源 |
|------|----------|--------|
| FarmAgent | SensorPanel | `GET /farm-agent/sensors?farm_id=X&days=7` |
| FarmAgent | FarmEventTimeline | `GET /farm-agent/events?farm_id=X&days=14` |
| FarmAgent | 场景选择器 + 注入按钮 | `GET /farm-agent/scenarios` + `POST /farm-agent/scenarios/:id/inject` |
| Farms | SeasonCard | `GET /farm-agent/seasons?farm_id=X&field_id=Y` |
| Farms | FarmEventTimeline (compact) | `GET /farm-agent/events?farm_id=X&field_id=Y&days=30` |
| Dashboard | HealthScoreCard | `listFarmProposals` + `listFarmTasks` 本地计算 |

任务完成时，`refreshWorkflow` 会失效 4 个查询键（proposals / tasks / sensors / events），触发前端自动刷新。

---

## 四、比赛演示场景机制

### 4.1 场景设计

同一农场（南京试验农场，3 个地块 A1/A2/A3），4 个时间点递进：

| scenario_id | 日期 | 地块 | 作物 | 生育期 | 关键感知 | 期望风险 |
|--------------|------|------|------|--------|----------|----------|
| `rainstorm` | 2026-07-18 | A1 | 水稻 | 分蘖期 | 土壤含水量 95%、降雨 158mm | `weather.rainstorm_drainage` high |
| `pest_outbreak` | 2026-07-25 | A2 | 玉米 | 拔节期 | 草地贪夜蛾 35 头/灯、被害率 18% | `pest.outbreak` high |
| `nutrient_deficiency` | 2026-08-02 | A3 | 大豆 | 开花期 | NDVI 0.42、速效氮 65 mg/kg | `nutrient.deficiency` medium |
| `drought` | 2026-08-12 | A1 | 水稻 | 抽穗期 | 土壤含水量 22%、12 天无雨 | `drought.stress` high |

### 4.2 Fixture 格式

每个场景对应一个 JSON fixture 文件（`app/data/demo_<scenario>_scenario.json`），包含：

```json
{
  "scenario_id": "rainstorm-v1",
  "label": "暴雨内涝",
  "description": "连续强降雨导致 A1 地块积水",
  "weather": { "rainfall_mm": 158, "consecutive_dry_days": 0, ... },
  "fields": [
    {
      "field_name": "A1",
      "crop_name": "水稻",
      "variety": "南粳46",
      "current_stage": "分蘖期",
      "sensors": [
        { "sensor_type": "soil_moisture", "value_float": 95.0, "unit": "%" },
        ...
      ]
    }
  ]
}
```

### 4.3 注入与幂等

`demo_scenario_service.inject_scenario_to_db` 的核心逻辑：

1. **按 field_name 匹配地块**：fixture 用 `field_name`（如 "A1"），注入时按农场 + 名称查找 `field_id`
2. **感知读数幂等**：用 `(field_id, sensor_type, scenario_id)` 去重，重复注入跳过
3. **茬次幂等**：用 `(field_id, season_code)` 查找已有茬次，存在则更新 `current_stage`，不存在则新建
4. **同步 `Field.current_season_id`**：注入后把地块的当前茬次指针指向新茬次

返回 `InjectionReport`，含 `created_sensors` / `skipped_sensors` / `created_seasons` / `updated_seasons` / `fields_covered`。

### 4.4 版本化

`scenario_id` 带 `-v1` 后缀（如 `rainstorm-v1`），未来可发布 `rainstorm-v2` 调整阈值或数据，旧版本仍可访问，保证演示可复现。

---

## 五、风险规则确定性保证

### 5.1 设计原则

风险判定**完全不调用 LLM**，用确定性阈值规则。理由：

1. **可复现**：比赛现场多次演示结果一致
2. **可审计**：每条风险的触发条件可追溯到具体阈值常量
3. **可解释**：证据链明确，评审能看清"为什么 high"

LLM 仅用于把风险转为结构化提案（`ProposalDraft`），不参与风险判定本身。

### 5.2 风险规则清单

| risk_key | 触发条件 | severity | 证据类型 |
|----------|----------|----------|----------|
| `weather.rainstorm_drainage` | 土壤含水量 ≥ 90% 且日降雨 ≥ 100mm | high | measured + rule |
| `pest.outbreak` | 虫情计数 ≥ 30 头/灯 | high | measured + rule |
| `pest.outbreak` | 虫情计数 ≥ 15 头/灯 | medium | measured + rule |
| `nutrient.deficiency` | NDVI < 0.5 且速效氮 < 80 mg/kg | medium | measured + rule |
| `drought.stress` | 土壤含水量 < 30% 且连续无雨 ≥ 7 天 | high | measured + rule |

阈值常量集中在 `farm_risk_service.py` 顶部（如 `_PEST_THRESHOLD_HIGH = 30`），便于按作物/区域调整。

### 5.3 证据链

每条 `FarmRisk` 携带 `evidence` 列表，每条证据含：

- `source_type`：数据来源类型（如 `sensor_reading`）
- `source_id`：数据来源 ID（如 `SensorReading.id`）
- `summary`：人类可读摘要
- `observed_at`：观测时间
- `fact_kind`：`measured`（实测）/ `rule`（规则）/ `inference`（推断）

高置信度提案（confidence ≥ 0.8）必须包含 `measured` 或 `rule` 证据，由 `ProposalDraft` 的 model_validator 强制。

---

## 六、任务状态机与事件溯源

### 6.1 任务状态机

```
pending ──start──▶ in_progress ──submit──▶ submitted
   │                   │                       │
   │                   │                  ┌────┴────┐
   │                   │              return    complete
   │                   │                  │       │
   │                   ▼                  ▼       ▼
   │              returned          returned  completed
   │                   │
   │              start/resubmit
   │                   │
   └───────────────────┘
   
   任意状态 ──cancel──▶ cancelled
```

每次状态转换都记录 `TaskExecutionAuditEntry`（actor / action / note / timestamp），不可篡改。

### 6.2 事件溯源

任务 `complete` 时，`farm_task_service.complete()` 执行：

1. 状态转换：`submitted` → `completed`
2. 写入 `TaskExecutionAuditEntry`
3. **插入 `FarmEvent`**：记录作业类型、投入品、操作人、关联任务 ID

这条 `FarmEvent` 是不可变的，会被下一轮 `build_snapshot` 的 `recent_events` 字段携带，让 Agent 在后续巡检中引用历史作业。

### 6.3 AI 记忆示例

演示 `drought` 场景时，Agent 在 snapshot 中看到 `recent_events` 含 25 天前的排水作业（rainstorm → drainage task completion），可在报告中引用：

> "7 月 18 日刚执行过排水作业，本轮转旱需注意水分管理切换，建议采用滴灌而非漫灌。"

这是单次推理做不到的——需要事件溯源支撑。

---

## 七、验证与测试覆盖

### 7.1 测试分层

| 层级 | 测试文件 | 覆盖内容 |
|------|----------|----------|
| ORM 模型 | `test_crop_season_lifecycle.py` | CropSeason CRUD + 字段约束 |
| 场景服务 | `test_demo_scenario_service.py` | fixture 加载 + 注入幂等 + Field 同步 |
| 风险规则 | `test_farm_risk_service_pest_nutrient_drought.py` | pest/nutrient/drought 阈值触发 + 证据链 |
| 任务事件流 | `test_farm_task_event_flow.py` | complete() 写 FarmEvent + 事件字段完整性 |
| Snapshot 聚合 | `test_farm_snapshot_service.py` | sensor_readings + recent_events 聚合 |
| 比赛种子 | `test_competition_demo_seed.py` | 4 个场景端到端种子验证 |
| API 契约 | `test_farm_agent_query_api.py` | 5 个 B9 endpoint 的 15 个契约测试 |

### 7.2 验证策略

- **确定性**：风险规则测试断言具体 risk_key 和 severity，不依赖 LLM
- **幂等性**：注入测试连续调用两次，断言第二次 `created_sensors=0`
- **隔离性**：每个测试用独立内存 SQLite，避免状态污染
- **契约一致性**：API 测试用 monkeypatch service 层，不依赖真实数据库

### 7.3 端到端验证

Week 4 的端到端验证流程：

1. 启动后端 + 前端
2. 创建农场 + 3 个地块（A1/A2/A3）
3. 依次注入 4 个场景，每次启动巡检，验证风险 + 提案
4. 每个场景：批准提案 → 任务生成 → 开始 → 提交 → AI 复核 → 人工完成 → 验证 FarmEvent 写入
5. 切换到 Farms 页面，验证茬次卡片与事件时间线更新
6. 切换到 Dashboard，验证健康分随风险数变化

---

## 八、关键设计决策

### 8.1 为什么用确定性规则而非 LLM 判定风险？

LLM 判定有随机性，同一输入可能产生不同 severity，无法保证比赛现场可复现。确定性规则把"判断"和"表达"分离：规则负责判断（确定性），LLM 负责把判断转为人类可读的提案（允许创造性）。

### 8.2 为什么移除 `_build_sensor_risks` 的 DB 回退路径？

B7 实现后 `build_snapshot` 总是聚合近 7 天 `SensorReading` 到 `snapshot.sensor_readings`，DB 回退路径冗余。更关键的是，回退路径会调用 `sqlite_manager.session()`，触发 `@event.listens_for(Engine, "connect")` 全局监听器注册，导致 `PRAGMA foreign_keys=ON` 污染所有后续 SQLite 引擎（包括测试内存引擎），引发测试间状态污染。移除回退路径根治了这个问题。

### 8.3 为什么用 SSE 而非 WebSocket？

Agent 执行是单向流式输出（server → client），SSE 足够且更简单。WebSocket 适合双向交互（如聊天），但巡检场景不需要客户端中途干预。SSE 还能复用 HTTP 基础设施（鉴权、代理、重试）。

### 8.4 为什么场景 scenario_id 带 `-v1` 后缀？

版本化保证演示可复现。未来发布 `rainstorm-v2` 调整阈值或数据时，旧版本仍可访问，已注入的 `sensor_readings.scenario_id` 不会失效。

### 8.5 为什么前端用暖色杂志风格？

farm-agent 相关组件（FarmRiskCard / SensorPanel / FarmEventTimeline / SeasonCard / HealthScoreCard）采用统一的暖色编辑风格（`bg-[#fffdf7]` + `border-[#ded5c5]` + `text-[#2e4036]`），与 Farms/Dashboard 原生 UI 视觉区分，让评审一眼看出"这是 AI 驾驶舱的数据呈现"。

---

## 附：核心文件索引

| 模块 | 文件 |
|------|------|
| 风险规则 | `app/services/farm_risk_service.py` |
| Snapshot 聚合 | `app/services/farm_snapshot_service.py` |
| 任务状态机 | `app/services/farm_task_service.py` |
| 场景注入 | `app/services/demo_scenario_service.py` |
| Agent 编排 | `app/services/farm_agent_service.py` |
| API 路由 | `app/api/v1/farm_agent.py` |
| 数据契约 | `app/schemas/farm_agent.py` |
| ORM 模型 | `app/models/farm.py`, `app/models/farm_agent.py` |
| 迁移 | `alembic/versions/008_*.py`, `alembic/versions/009_*.py` |
| 前端页面 | `frontend-react/src/pages/FarmAgent.tsx`, `Farms.tsx`, `Dashboard.tsx` |
| 前端组件 | `frontend-react/src/components/farm-agent/*.tsx` |
