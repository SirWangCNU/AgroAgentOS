# AgroAgentOS 农业智能体需求分析文档 — 编写计划

> 本文件是 Plan Mode 的产物，描述将要生成的需求分析文档结构、各章节要点与素材来源。
> 用户接受本计划后，执行阶段会基于此计划在 `docs/` 目录下生成正式文档：`docs/REQUIREMENTS_ANALYSIS.md`。

---

## 一、任务理解与目标

### 1.1 用户原始诉求

用户原话：
> "我现在有点不知道哪些功能是该怎么执行使用我这个智能体了，我到底要做什么这些功能模块怎样结合起来来参加这个人工智能比赛，我要的是农业智能体，给我做出一份详细的需求分析文档我来仔细查看和修改，根据已有功能"

三个核心痛点：
1. **功能多但无主线**：9 个 Skill + 12 个前端页面 + 5 个 MCP server + RAG 三层流水线 + 4 个演示场景，用户自己都搞不清"哪个功能该在什么时候用"。
2. **比赛故事未成形**：已有的 `competition-architecture.md` 偏技术架构，`competition-demo-script.md` 偏演示操作步骤，但**没有一份文档能把"智能体能做什么 + 为谁做 + 怎么用 + 比赛讲什么故事"串成一条线**。
3. **要"农业智能体"**：必须以智能体为主线（不是 IoT 平台、不是农场 ERP），所有功能都围绕"Agent 怎么决策、怎么闭环"展开。

### 1.2 文档定位

- **类型**：综合需求分析文档（PRD + 参赛方案 + 使用手册 三者融合）
- **视角**：以智能体为主线，从"能力 → 场景 → 闭环 → 演示"层层递进
- **篇幅**：详细（用户要"仔细查看和修改"），约 8000-12000 字
- **避免重复**：
  - 不复写 `competition-architecture.md` 的技术栈分层、ORM 模型字段、代码路径索引
  - 不复写 `competition-demo-script.md` 的 10 步操作剧本
  - 而是从**业务/产品/参赛**视角重新组织，让用户从"功能堆砌"中跳出来看主线

### 1.3 与已有文档的关系

| 已有文档 | 视角 | 与本需求文档的关系 |
|---|---|---|
| `docs/architecture.md` | 系统架构 | 本文档引用其"感知-认知-决策-执行-反馈"闭环概念，但不深入代码层 |
| `docs/competition-architecture.md` | 比赛技术架构 | 本文档引用其"风险规则确定性保证"等设计决策，但聚焦业务价值而非实现 |
| `docs/competition-demo-script.md` | 14 分钟演示操作 | 本文档在"演示故事线"章节会引用其场景表，但简化为业务流程而非操作步骤 |
| `docs/PHASE_PLAN.md` | 阶段路线图 | 本文档"迭代规划"章节会对比已有阶段，标注"已完成/进行中/未来" |
| `AGENTS.md` | 开发规范 | 不重复，仅在文档末尾以"开发约束参考"链接 |

---

## 二、文档目标读者

文档面向三类读者，每个章节会标注主要受众：

| 读者 | 关心什么 | 对应章节 |
|---|---|---|
| **你自己（项目所有者）** | 我到底做了什么、怎么用、参赛讲什么 | 全文，特别是「核心价值主张」「智能体能力矩阵」「演示故事线」 |
| **比赛评委** | 这是什么、为什么有创新、技术深度如何、能否落地 | 「项目概述」「核心创新」「端到端闭环」「演示场景」 |
| **未来协作者/继承者** | 模块如何联动、智能体如何决策、如何扩展 | 「功能模块清单」「Agent 决策流程」「模块联动关系」 |

---

## 三、文档章节大纲（执行阶段按此生成）

### 第 1 章：项目概述

**目的**：用一段话讲清楚"这是什么"。

**内容要点**：
- **一句话定位**：AgroAgentOS 是基于 LangGraph 多智能体的农场行动闭环平台，用确定性规则 + LLM 推理 + 人工审批，把"感知-认知-决策-执行-反馈"做成可审计的完整闭环。
- **关键差异化**（对标分析）：
  - vs 大疆农业 / 极飞：偏 IoT 数据采集，缺 AI 决策闭环
  - vs John Deere Operations Center / Climate FieldView：偏经营管理，缺人机协同审批
  - vs 智农云 / 沣翼云：偏 SaaS 工具，缺智能体推理
  - **AgroAgentOS 的独特定位**：把"AI 起草 + 人工审批 + 事件溯源形成 AI 记忆"做成了完整闭环，且**无硬件依赖**（fixture 注入可复现）
- **核心价值主张（3 句话）**：
  1. 给农户/农技员：一个能"看农场、判风险、起草提案、跟踪执行"的 AI 副驾驶
  2. 给农场主/合作社：可审计的农事决策流水线，每条风险都有证据链
  3. 给评委：用确定性规则保证可复现，用 LLM 保证创造性表达，用人审保证安全边界

**素材来源**：`competition-architecture.md` §1.1-1.3、`architecture.md` 的整体设计

---

### 第 2 章：目标用户与使用场景

**目的**：回答"为谁做"。

**内容要点**：
- **三类典型用户画像**：
  - **农户/家庭农场主**：自有几十亩地，需要决策辅助（什么时候打药、施肥、灌溉）
  - **农技员/合作社管理员**：管多个地块，需要批量巡检和任务派发
  - **农业科研/教学场景**：做农业数字化试点，需要可复现的演示环境
- **三类使用场景**：
  - **场景 A：日常咨询**（聊天 + 知识库）— 农户问"水稻分蘖期怎么管"
  - **场景 B：紧急响应**（巡检 + 提案）— 暴雨后 AI 主动识别风险并起草排水提案
  - **场景 C：周期管理**（茬次 + 任务 + 事件）— 从播种到收获的全周期数字化

**素材来源**：基于 9 个 Skill 的 triggers 和 `competition-demo-script.md` 的 4 个场景归纳

---

### 第 3 章：智能体能力矩阵（核心章节）

**目的**：把 9 个 Skill 按"业务域 + 触发场景 + 输入输出 + 风险等级"整理成一张清晰的能力矩阵，让用户一眼看清"智能体能干什么"。

**内容要点**：

#### 3.1 能力总览表

| Skill | 业务域 | 解决什么问题 | 典型触发语 | 输入 | 输出 | 风险等级 |
|---|---|---|---|---|---|---|
| agriculture_qa | 通用问答 | 农业常识问答 | "什么是分蘖期" | 文本问题 | Markdown 答案 + RAG 引用 | low |
| crop_advisory | 种植顾问 | 按作物阶段给种植建议 | "水稻拔节期怎么施肥" | 作物 + 阶段 | N/P/K 配比建议 | low |
| pest_diagnosis | 病虫害诊断 | 根据症状诊断病害 | "水稻叶子有斑点怎么办" | 症状描述 | 诊断 + 防治方案 | low |
| weather_advice | 气象农事 | 天气驱动的农事决策 | "明天能打药吗" | 位置 + 日期 | 天气 + 农事建议（含决策规则） | low |
| market_intelligence | 市场行情 | 农产品销售策略 | "玉米现在卖合算吗" | 作物 + 位置 | 价格 + 供需 + 政策 + 销售建议 | low |
| marketing_generator | 营销内容 | 生成营销文案 | "帮我写个番茄抖音脚本" | 产品 + 平台 + 风格 | 5 类营销内容 | low |
| knowledge_retrieval | 知识检索 | 精确知识查询 | "查一下稻瘟病防治" | 查询词 | 文档片段 + 来源 | low |
| farm_inspection | 综合巡检 | 主动识别农场风险并起草提案 | （后端触发，非用户直接调用） | farm_id | 风险列表 + pending 提案 | medium |
| farm_task_verification | 任务验收 | AI 复核作业证据 | （任务提交后触发） | task_id + 证据 | verdict 草稿（pass/rework/...） | medium |

#### 3.2 智能体决策流程（一图说清）

LangGraph 5 节点：
```
SkillRouter → Planner → Executor → Replanner (loop) → END
```
- 每个节点的输入输出、为什么这样设计（一句话）
- 二级 Subagent：farm_data_analyst / agronomy_researcher / farm_work_planner
- 防死循环机制：iteration 上限、tried_skills 黑名单、inside_fork 标记

#### 3.3 工具白名单（智能体可调用什么）

| 类别 | 工具 | 用途 |
|---|---|---|
| 知识 | search_knowledge_base | RAG 检索（BM25 + Vector + RRF + Rerank） |
| 时间 | get_current_time | 时区感知时间 |
| 天气 | get_weather / get_weather_forecast | 实时 + N 天预报 + 极端天气预警 |
| 节气 | solar_term_reminder / generate_planting_calendar | 节气提醒 + 全年种植历 |
| 市场 | get_market_price / get_supply_demand / get_policy_subsidies / get_market_analysis | 市场行情四件套 |
| Farm Agent | get_farm_snapshot / inspect_farm_weather_risks / get_field_work_quality / get_pending_farm_tasks / get_task_evidence / create_action_proposal / save_task_verification_draft | 7 个受控工具 |
| MCP | web_search / system / network / docker / winlog | 5 个远程 MCP server（联网搜索 + 系统诊断） |

#### 3.4 权限三层防御（智能体的安全边界）

- Layer 0: Skill allowlist 硬墙（任何 mode 都得过）
- Layer 1: Mode 限制（READ_ONLY / NORMAL / ASK_DESTRUCTIVE / BYPASS）
- Layer 2: 静态 Guardrails（高危/通知黑名单）
- **关键设计**：受控 Farm Skill（farm_inspection / farm_task_verification）必须严格走 playbook 白名单，AI 不能跨越"人工审批"双门

**素材来源**：
- 9 个 `SKILL.md` 文件
- `app/agents/graph.py`、`app/agents/subagents/__init__.py`
- `app/tools/meta.py`（23 个 ToolMeta）
- `app/runtime/permissions.py`

---

### 第 4 章：功能模块清单（按业务域）

**目的**：从产品视角盘点"用户能看到哪些功能"，而不是从代码视角。

**内容要点**：

#### 4.1 模块地图

```
AgroAgentOS 农业智能体平台
├─ 对话与知识（AI 入口）
│  ├─ AI 对话（Chat）— SSE 流式 + RAG 引用 + 多轮记忆
│  ├─ 智能体能力中心（AgentCapabilities）— Skill 一键体验
│  └─ 知识库管理（Knowledge）— 文档上传/删除
│
├─ 农场运营（事实底座）
│  ├─ 农场管理（Farms）— 农场/地块/茬次 CRUD
│  ├─ 农场地图（FarmMap）— Leaflet 地图可视化
│  └─ 作业轨迹（Trajectory）— Excel 上传 + 质量分析
│
├─ AI 驾驶舱（决策中枢）★ 核心
│  ├─ 综合巡检（FarmAgent）— SSE 流式 + 风险态势
│  ├─ 行动提案（ActionProposal）— 人工审批
│  ├─ 任务看板（FarmTaskBoard）— 4 列状态机
│  ├─ 感知面板（SensorPanel）— 7 天感知数据
│  ├─ 事件流（FarmEventTimeline）— 14 天事件流
│  └─ 演示场景注入（ScenarioInjector）— 4 个比赛场景
│
├─ 决策辅助工具（独立工具页）
│  ├─ 天气查询（Weather）— 当前 + 5 天预报 + 农事建议
│  ├─ 病虫害诊断（PestDiagnosis）— 表单 + 流式诊断
│  ├─ 市场行情（MarketPrice）— 价格 + 供需 + 政策 + AI 分析
│  └─ 视频生成（VideoGen）— 文本/图片 → 视频（火山引擎 Seedance）
│
├─ 经营仪表盘（Dashboard）
│  ├─ 今日决策台（4 卡片：风险数/提案数/任务数/巡检状态）
│  ├─ 农场健康分（公式：100 - 高风险×20 - 中风险×10 - 逾期任务×5）
│  └─ 系统状态 + 功能九宫格
│
└─ 系统管理
   ├─ 用户管理（Users）— 仅管理员
   ├─ 个人中心（Profile）
   └─ 健康检查（Health）— liveness + readiness
```

#### 4.2 各模块功能详解（每个模块一段）

每个模块按以下结构写：
- **入口路由**：哪个 URL
- **核心功能**：3-5 条要点
- **数据来源**：调用哪些 API
- **与智能体的关系**：是 Skill 入口 / 数据底座 / 输出展示
- **典型用户故事**：1 句话

**素材来源**：12 个前端页面 + 18 个 API router + 27 个 service

---

### 第 5 章：端到端业务闭环（核心章节）

**目的**：用一张图 + 一段叙事把"感知-认知-决策-执行-反馈"讲清楚，这是参赛的**核心故事线**。

**内容要点**：

#### 5.1 闭环图（来自 competition-architecture.md §3.2）

```
感知注入              认知                决策              执行              反馈
   │                  │                  │                │                 │
   ▼                  ▼                  ▼                ▼                 ▼
SensorReading   farm_risk_service    Proposal         FarmTask          FarmEvent
   │                  │                  │                │                 │
   └──── build_snapshot ──┘              │                │                 │
                          approve/reject │                │                 │
                                         ▼                ▼                 │
                                  start/submit/complete ──────────────────►│
                                                                            │
                          下一轮 snapshot 携带 recent_events ◄─────────────┘
```

#### 5.2 五个阶段的角色与产物

| 阶段 | 角色 | 输入 | 输出 | 关键技术 |
|---|---|---|---|---|
| 感知 | IoT/fixture | 天气、传感器读数 | `SensorReading` 表 | demo_scenario_service 幂等注入 |
| 认知 | AI（确定性规则） | snapshot | `FarmRisk` 列表（含证据链） | farm_risk_service 阈值规则 |
| 决策 | AI（LLM）+ 人工 | risk + playbook | `FarmActionProposal`（pending） | LangGraph + ProposalDraft |
| 执行 | 作业人员 | approved proposal | `FarmTask` 状态机 + 证据 | FarmTaskBoard |
| 反馈 | AI 复核 + 人工 | task evidence | `FarmEvent`（不可变） | task_verification + 事件溯源 |

#### 5.3 AI 记忆机制（差异化亮点）

- 任务完成时 `farm_task_service.complete()` 自动写 `FarmEvent`
- 下一轮 `build_snapshot` 的 `recent_events` 字段携带历史事件
- Agent 在新巡检中可引用"7 天前刚排过水"等连贯上下文
- **这是单次推理做不到的，需要事件溯源支撑**

#### 5.4 人工审批双门（安全边界）

- **门 1**：批准提案（pending → approved → FarmTask）
- **门 2**：完成任务（submitted → completed → FarmEvent）
- AI 不能跨越任何一道门，只能起草/复核

**素材来源**：`competition-architecture.md` §3.1-3.2、§5-6、`farm_agent_service.py`

---

### 第 6 章：演示场景设计

**目的**：把 4 个比赛演示场景串成一个完整故事，回答"参赛到底演示什么"。

**内容要点**：

#### 6.1 四场景时间线

| scenario_id | 日期 | 地块 | 作物 | 生育期 | 关键感知 | 期望风险 | 期望提案 |
|---|---|---|---|---|---|---|---|
| rainstorm | 2026-07-18 | A1 | 水稻 | 分蘖期 | 土壤含水量 95%、降雨 158mm | `weather.rainstorm_drainage` high | 排水清沟 |
| pest_outbreak | 2026-07-25 | A2 | 玉米 | 拔节期 | 草地贪夜蛾 35 头/灯、被害率 18% | `pest.outbreak` high | 喷药防治 |
| nutrient_deficiency | 2026-08-02 | A3 | 大豆 | 开花期 | NDVI 0.42、速效氮 65 mg/kg | `nutrient.deficiency` medium | 追施肥料 |
| drought | 2026-08-12 | A1 | 水稻 | 抽穗期 | 土壤含水量 22%、12 天无雨 | `drought.stress` high | 灌溉补水 |

#### 6.2 四场景串联的故事线（核心叙事）

**关键洞察**：4 个场景不是孤立的，而是**同一农场不同时间点的演进**，能展示 AI 的"记忆"能力：

> "7 月 18 日 rainstorm 场景，AI 起草排水提案 → 人工批准 → 任务执行 → 写入 FarmEvent。
> 7 月 25 日切换到 pest_outbreak 场景，AI 在巡检 A2 玉米时，能从 recent_events 看到 7 天前 A1 的排水作业，在报告中给出连贯建议。
> 8 月 12 日 drought 场景，AI 看到 25 天前的排水事件，在报告中提示'刚排过水，本轮转旱需注意水分管理切换，建议采用滴灌而非漫灌'。"

#### 6.3 4 个风险规则（确定性保证）

| risk_key | 触发条件 | severity |
|---|---|---|
| `weather.rainstorm_drainage` | 土壤含水量 ≥ 90% 且日降雨 ≥ 100mm | high |
| `pest.outbreak` | 虫情计数 ≥ 30 头/灯 | high |
| `nutrient.deficiency` | NDVI < 0.5 且速效氮 < 80 mg/kg | medium |
| `drought.stress` | 土壤含水量 < 30% 且连续无雨 ≥ 7 天 | high |

**关键设计**：风险判定**完全不调用 LLM**，用确定性阈值规则 → 比赛现场多次演示结果一致 → 评审能看清"为什么 high"

**素材来源**：`competition-architecture.md` §4-5、`competition-demo-script.md` 附录

---

### 第 7 章：模块联动关系

**目的**：回答"功能模块怎样结合起来"。

**内容要点**：

#### 7.1 联动关系图

```
                    ┌─────────────────────┐
                    │   智能体能力中心     │ ← 9 个 Skill 一键体验
                    │ (AgentCapabilities) │
                    └──────────┬──────────┘
                               │ 用户点击示例问题
                               ▼
                    ┌─────────────────────┐
                    │     AI 对话          │ ← LangGraph 主入口
                    │      (Chat)         │
                    └──────────┬──────────┘
                               │ 用户提问 / 巡检触发
                               ▼
        ┌──────────────────────────────────────────────┐
        │              LangGraph 多智能体                │
        │  SkillRouter → Planner → Executor → Replanner │
        └──────┬───────────┬──────────────┬────────────┘
               │           │              │
               ▼           ▼              ▼
        ┌──────────┐ ┌──────────┐  ┌──────────────┐
        │ RAG 知识 │ │ 工具调用 │  │  Subagent    │
        │  9 文档  │ │ 23 个    │  │ 3 个二级     │
        └──────────┘ └──────────┘  └──────────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │   AI 驾驶舱         │ ← 决策中枢
                    │   (FarmAgent)       │
                    └──────────┬──────────┘
                               │
              ┌────────────────┼────────────────┐
              ▼                ▼                ▼
        ┌──────────┐    ┌──────────┐    ┌──────────────┐
        │ 农场管理 │    │ 任务看板 │    │  感知面板    │
        │ (Farms)  │    │(Tasks)   │    │ (Sensors)    │
        └────┬─────┘    └────┬─────┘    └──────┬───────┘
             │               │                 │
             └───────────────┼─────────────────┘
                             ▼
                    ┌─────────────────────┐
                    │   经营仪表盘        │ ← 全局视图
                    │   (Dashboard)       │
                    └─────────────────────┘
```

#### 7.2 三大联动主线

**主线 A：从对话到行动（轻量场景）**
```
用户在 Chat 问"水稻分蘖期怎么管"
→ SkillRouter 选 crop_advisory
→ Executor 调 search_knowledge_base + get_weather
→ Replanner 合成报告
→ 用户得到 Markdown 答案 + RAG 引用
```

**主线 B：从巡检到任务（核心闭环）**
```
用户在 FarmAgent 选择场景 + 注入感知 + 启动巡检
→ farm_inspection Skill 调用 5 个 farm_agent_tools
→ 风险识别 + 起草 pending 提案
→ 用户在 ActionProposalCard 批准
→ 提案转 FarmTask（pending）
→ 用户在 FarmTaskBoard 完成 start → submit → complete
→ AI 自动 task_verification 生成 verdict 草稿
→ complete 时自动写 FarmEvent
→ 下次巡检 snapshot 携带 recent_events
```

**主线 C：从农场到 Dashboard（全局视图）**
```
用户在 Farms 创建农场 + 地块 + 茬次
→ FarmAgent 巡检生成风险 + 提案 + 任务
→ Dashboard 健康分公式实时计算
→ 健康分 = 100 - 高风险×20 - 中风险×10 - 逾期任务×5
→ 用户从 Dashboard 一眼看清农场运营状态
```

#### 7.3 数据流（哪些表被谁读写）

| 表 | 写入方 | 读取方 |
|---|---|---|
| `farms` / `fields` | 用户（Farms 页） | FarmAgent、Dashboard |
| `crop_seasons` | 用户 + demo_scenario_service | FarmAgent、Farms |
| `sensor_readings` | demo_scenario_service（+ 未来 IoT） | FarmAgent、Dashboard |
| `farm_action_proposals` | farm_inspection Skill | FarmAgent、Dashboard |
| `farm_tasks` | farm_proposal_service（approve 后） | FarmAgent、Dashboard |
| `farm_events` | farm_task_service.complete() | FarmAgent、Farms、Dashboard |
| `chat_sessions` / `chat_session_messages` | Chat 页 | Chat 页 |
| `trajectory_files` / `trajectory_points` | 用户（Farms 页上传） | Farms、FarmAgent |

**素材来源**：前端路由 + `competition-architecture.md` §3.3

---

### 第 8 章：典型用户故事（5 个端到端故事）

**目的**：用"用户视角"的故事让评委/读者快速理解"这个智能体怎么用"。

每个故事结构：**用户身份 → 目标 → 操作步骤 → 智能体行为 → 结果**

#### 故事 1：农户日常咨询（轻量）
- 用户：家庭农场主，自有 50 亩水稻
- 目标：了解水稻分蘖期管理要点
- 操作：进入 Chat → 输入"水稻分蘖期怎么管"
- 智能体：SkillRouter 选 crop_advisory → 调 RAG → 合成报告
- 结果：得到含 N/P/K 配比建议的 Markdown 答案

#### 故事 2：暴雨应急响应（核心闭环）
- 用户：合作社管理员，管 3 个地块
- 目标：暴雨后识别风险并派工
- 操作：进入 FarmAgent → 选择 rainstorm 场景 → 注入感知 → 启动巡检
- 智能体：farm_inspection Skill → 调 5 个工具 → 起草排水提案
- 操作（续）：批准提案 → 任务生成 → 作业人员执行 → AI 复核 → 完成
- 结果：FarmEvent 写入"排水清沟"事件，下次巡检 AI 可引用

#### 故事 3：虫害精准防治
- 用户：农技员
- 目标：诊断玉米虫害并制定防治方案
- 操作：在 PestDiagnosis 页提交症状 → AI 流式诊断 → 进入 Chat 追问
- 智能体：pest_diagnosis Skill → RAG + 知识库图谱 → 给出化学+生物防治方案
- 结果：得到含农药选择、用量、安全间隔期的完整方案

#### 故事 4：销售时机决策
- 用户：种玉米的农户
- 目标：判断玉米现在卖合算吗
- 操作：进入 MarketPrice → 输入"玉米 + 北京"
- 智能体：market_intelligence Skill → 调 4 个市场工具 → LLM 综合分析
- 结果：得到价格摘要 + 走势预测 + 供需分析 + 政策补贴 + 销售建议 + 风险提示

#### 故事 5：农事安排与天气协同
- 用户：大棚种植户
- 目标：明天能打药吗
- 操作：进入 Chat → 输入"明天能打药吗"
- 智能体：SkillRouter 检测到 weather_advice + pest_diagnosis 协同 → 合并 playbook → 调 get_weather_forecast → 应用决策规则（降雨>70% 不建议、风速>4 级不建议）
- 结果：得到"明天下午 2 点后降雨概率 80%，不建议打药，建议推迟到后天上午"的精准建议

**素材来源**：9 个 Skill 的 examples 字段 + `skill_router.py` 的协同模式

---

### 第 9 章：核心创新点与比赛亮点

**目的**：直接告诉评委"这个项目牛在哪"。

**内容要点**（5 大创新点）：

#### 创新点 1：可审计的农场行动闭环
- 业内首个把"感知-认知-决策-执行-反馈"做成完整闭环的农业 Agent
- 每条风险带完整证据链（measured + rule + inference）
- 每个任务有 `TaskExecutionAuditEntry` 不可篡改审计日志

#### 创新点 2：确定性规则 + LLM 表达的分离设计
- 风险判定：纯规则（阈值常量集中在 `farm_risk_service.py` 顶部）
- 提案生成：LLM（允许创造性表达）
- **价值**：可复现 + 可审计 + 可解释 + 现场不翻车

#### 创新点 3：人工审批双门 + AI 记忆
- 双门：批准提案、完成任务，AI 不能跨越
- 记忆：`FarmEvent` 不可变事件流 + 下一轮 snapshot 携带 `recent_events`
- **价值**：人机协同安全边界 + 跨场景连贯决策

#### 创新点 4：多智能体协同 + 二级 Subagent
- LangGraph 主图（5 节点）+ 3 个二级 Subagent（数据分析师/农艺研究员/行动规划师）
- 协同技能模式（如 weather_advice + pest_diagnosis 同时触发）
- **价值**：复杂问题分解 + 专业分工

#### 创新点 5：无硬件依赖的可复现演示
- 4 个 fixture 场景（rainstorm/pest_outbreak/nutrient_deficiency/drought）
- 幂等注入（重复注入不产生重复数据）
- 版本化（scenario_id 带 `-v1` 后缀）
- **价值**：比赛现场稳定演示 + 接入真实硬件只需替换数据源

**素材来源**：`competition-architecture.md` §8 关键设计决策

---

### 第 10 章：已有功能 vs 比赛要求

**目的**：诚实盘点"已完成什么、还有什么 gap"。

**内容要点**：

#### 10.1 已完成功能清单（按完整度分级）

| 完整度 | 功能 | 状态 |
|---|---|---|
| ★★★ 完整可用 | AI 对话、RAG 检索、农场 CRUD、Farm Agent 巡检闭环、4 个演示场景、健康检查 | 可直接演示 |
| ★★☆ 可用但有 gap | 视频生成（依赖火山引擎）、市场行情（依赖外部数据源）、天气（依赖和风 API） | 需配置 API Key |
| ★☆☆ 占位/原型 | 营销生成页（前端模拟未接 API）、History 页（孤儿未注册路由） | 需补全或删除 |

#### 10.2 比赛常见评分维度对照

| 评分维度（通用） | 本项目表现 | 证据 |
|---|---|---|
| 技术创新性 | ★★★★★ | LangGraph 多智能体 + 确定性规则 + 事件溯源 |
| 落地可行性 | ★★★★☆ | 无硬件依赖 + 接入真实 IoT 仅需替换数据源 |
| 社会价值 | ★★★★★ | 服务农业数字化、乡村振兴战略 |
| 工程完整度 | ★★★★☆ | 前后端分离 + 测试覆盖 + 文档齐全 |
| 演示效果 | ★★★★☆ | 4 场景串成故事 + SSE 流式可观察 |
| 可扩展性 | ★★★★☆ | Skill 热插拔 + MCP 工具协议 + LLM 三层 fallback |

#### 10.3 已知 gap 与建议

| Gap | 建议处理 | 优先级 |
|---|---|---|
| 营销页未接 API | 比赛前删除入口，或接入 LLM 实现简单文案生成 | P1 |
| History 孤儿页 | 比赛前删除文件 | P2 |
| 缺少真实 IoT 接入 | 演示时强调"fixture 是可替换的数据源"，不影响闭环逻辑 | P0（已用演示场景替代） |
| 知识库覆盖有限（9 篇 MD） | 比赛前可补充 2-3 篇（如智能灌溉、精准农业） | P2 |
| 没有 PPT 大纲 | 本文档第 11 章提供 | P0 |

**素材来源**：12 个前端页面的实际状态、`competition-architecture.md` §7 测试覆盖

---

### 第 11 章：比赛展示建议

**目的**：给用户一份"参赛要讲什么"的清单。

**内容要点**：

#### 11.1 一句话电梯演讲

> "AgroAgentOS 是一个用 LangGraph 多智能体打造的农场行动闭环平台——AI 巡检识别风险并起草提案，人工审批后转为可执行任务，任务完成自动写回事件流形成 AI 记忆，下一轮巡检可引用历史决策。我们用确定性规则保证比赛现场可复现，用 4 个递进场景展示同一农场的演进故事。"

#### 11.2 5 分钟版演示主线（精简版）

1. **30 秒**：项目定位 + 闭环概念
2. **90 秒**：rainstorm 场景注入 + AI 巡检 + 风险卡片
3. **90 秒**：批准提案 + 任务执行 + FarmEvent 写入
4. **60 秒**：切换 pest_outbreak 场景 + 展示 AI 记忆（引用排水事件）
5. **30 秒**：核心创新点 + 未来展望

#### 11.3 答辩常见问题预案

| 问题 | 答案要点 |
|---|---|
| "为什么不用 LLM 直接判定风险？" | 确定性规则可复现、可审计、可解释，LLM 仅负责创造性表达 |
| "如何接入真实硬件？" | 替换 `sensor_readings` 表的写入来源即可，上层逻辑零改动 |
| "和已有的智慧农业平台有什么区别？" | 我们做的是"决策闭环"而非"数据采集"或"经营管理" |
| "AI 会不会越权执行？" | 双门设计：批准提案、完成任务都需要人工，AI 只能起草/复核 |
| "如何保证数据安全？" | 所有权校验贯穿 + JWT 鉴权 + Pydantic 类型校验 + MCP 黑名单防 prompt injection |
| "如何扩展新的农业场景？" | 新增 SKILL.md + 工具实现 + 测试，热插拔无需重启 |

#### 11.4 PPT 大纲建议（10 页）

1. 封面 + 项目名
2. 问题域：农业决策依赖经验，缺数据闭环
3. 解决方案：AgroAgentOS 闭环架构图
4. 核心创新：5 大创新点
5. 演示场景：4 场景时间线
6. 演示流程：rainstorm 场景截图
7. 技术架构：LangGraph + RAG + 工具协议
8. 差异化：vs 大疆/JD Operations Center/智农云
9. 路线图：未来 3 个月规划
10. 团队 + 致谢

**素材来源**：`competition-demo-script.md` §五 答疑要点

---

### 第 12 章：迭代规划（已有 vs 未来）

**目的**：在已有 `PHASE_PLAN.md` 基础上，标注当前进度并给出比赛前后的建议。

**内容要点**：

#### 12.1 当前完成度（截至 2026-07-20）

| 阶段 | 模块 | 状态 | 备注 |
|---|---|---|---|
| Phase 1-3 | 问答 Agent + RAG + 工具协议 | ✅ 已完成 | 9 个 Skill 全部 inline 可用 |
| Phase 4 | 农场/地块管理 | ✅ 已完成 | Farm/Field/CropSeason CRUD |
| Phase 5 | 农事管理（Activity） | ✅ 已完成（变种） | 实际实现为 FarmEvent + FarmTask，比原计划更贴合 Agent 闭环 |
| Phase 6 | 生长预测 | ❌ 未实现 | 暂未做，比赛非必需 |
| Phase 7 | 智能预警 | 🟡 部分实现 | Farm Agent 巡检相当于被动预警，缺主动定时检查 |
| **额外** | **Farm Agent 闭环** | ✅ **已完成** | **比原计划多做的核心模块**，是比赛主亮点 |
| **额外** | **演示场景注入** | ✅ **已完成** | 4 个 fixture 场景 |
| **额外** | **二级 Subagent** | ✅ **已完成** | 3 个专业 Subagent |
| **额外** | **任务核验 AI 复核** | ✅ **已完成** | task_verification Skill |

#### 12.2 比赛前建议（必做 / 选做）

**必做（P0）**：
- [ ] 跑通 4 个场景的端到端演示（按 `competition-demo-script.md` 10 步剧本）
- [ ] 清理孤儿页面（History.tsx + api/history.ts）
- [ ] 营销页要么补全要么隐藏入口
- [ ] 准备 PPT（参考第 11.4 大纲）
- [ ] 验证 LLM API Key 配置正常

**选做（P1）**：
- [ ] 补充 2-3 篇知识库文档（智能灌溉、精准农业）
- [ ] 增加一个"未来场景 v2"展示扩展性
- [ ] 录制 5 分钟演示视频作为备份

#### 12.3 比赛后路线图（3-6 个月）

- **Q1 2026**：接入真实 IoT（MQTT 协议）+ 移动端适配
- **Q2 2026**：实现 Phase 6 生长预测（基于历史数据 + 天气）+ Phase 7 主动预警引擎
- **Q3 2026**：多农场租户隔离 + 农事协作（多用户角色）+ 数据分析仪表盘
- **Q4 2026**：开放 Skill SDK + MCP 工具市场

**素材来源**：`PHASE_PLAN.md` + 当前实际代码状态

---

### 附录

#### 附录 A：核心文件索引

只列对理解需求最重要的 15-20 个文件，不重复 `competition-architecture.md` 的完整索引。

| 类别 | 文件 |
|---|---|
| Agent 主图 | `app/agents/graph.py` |
| Skills 定义 | `app/skills/definitions/*/SKILL.md`（9 个） |
| Farm Agent 服务 | `app/services/farm_agent_service.py`、`farm_risk_service.py`、`farm_proposal_service.py`、`farm_task_service.py` |
| 演示场景 | `app/data/demo_*_scenario.json`（4 个）、`app/services/demo_scenario_service.py` |
| 前端核心 | `frontend-react/src/pages/FarmAgent.tsx`、`Farms.tsx`、`Dashboard.tsx`、`Chat.tsx` |
| 配置 | `app/config.py` |

#### 附录 B：术语表

| 术语 | 含义 |
|---|---|
| Skill | 智能体能力单元，YAML frontmatter + Markdown playbook |
| Proposal | AI 起草的待审批行动提案 |
| Task | 人工批准后创建的执行任务 |
| FarmEvent | 不可变事件流，AI 记忆的基础 |
| Snapshot | 农场快照，包含 fields/sensors/recent_events |
| RRF | Reciprocal Rank Fusion，混合检索融合算法 |
| Subagent | 二级智能体，主 Executor 委托执行 |
| Fixture | 比赛演示用的预设感知数据 JSON 文件 |

#### 附录 C：开发约束参考

- 遵守 `AGENTS.md` 与 `docs/DEVELOPMENT_STANDARDS.md`
- 修改前必读现有实现 + 相邻测试 + `git status`
- 禁止覆盖用户改动、顺手重构、吞异常、弱化测试
- 完成后必跑相关验证并如实报告

---

## 四、执行阶段产出

用户接受本计划后，会按本大纲生成正式文档：

- **文件路径**：`e:\GithubProgram\AgroAgentOS\docs\REQUIREMENTS_ANALYSIS.md`
- **预计字数**：8000-12000 字（中文）
- **格式**：Markdown，含表格、流程图（ASCII）、章节锚点
- **不创建其他文件**：仅生成这一份需求分析文档，不改动代码

## 五、验证步骤

文档生成后，用户可通过以下方式验证：

1. **完整性**：对照本计划第 3 章的 12 个章节大纲，确认每章都已生成
2. **准确性**：随机抽 3-5 个功能点，对照实际代码（如 SKILL.md、API 路由）确认描述无误
3. **可读性**：从第 1 章读到第 12 章，确认逻辑递进、无重复、无矛盾
4. **可修改性**：文档结构清晰、章节独立，用户可方便地增删改

---

## 六、关键决策记录

| 决策点 | 选择 | 理由 |
|---|---|---|
| 文档类型 | 综合（PRD + 参赛方案 + 使用手册） | 用户跳过了 AskUserQuestion，按"详细"诉求做最完整版本 |
| 主线 | 以智能体为主线 | 用户明确说"我要的是农业智能体" |
| 篇幅 | 详细（8000-12000 字） | 用户原话"详细的需求分析文档我来仔细查看和修改" |
| 是否包含未来规划 | 包含但与已有功能分开 | 用户说"根据已有功能"，但比赛通常需要展示愿景，故放第 12 章独立讨论 |
| 是否重复已有文档 | 不重复，引用即可 | `competition-architecture.md` 和 `competition-demo-script.md` 已存在，新文档应补充而非覆盖 |
| 文件位置 | `docs/REQUIREMENTS_ANALYSIS.md` | 与其他 docs 同级，命名清晰 |
