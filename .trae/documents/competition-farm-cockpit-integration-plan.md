# 比赛场景：农场管理 ↔ AI 农场驾驶舱联动闭环计划

> **窗口**：3-4 周 ｜ **形态**：先演示后自由 ｜ **范围**：核心闭环 + 茬次维度 + 4 个场景 + 轻量注入 UI
> **不做**：真实硬件接入、卫星 API、处方图空间化、IoT 协议适配

---

## 一、Summary（摘要）

在 3-4 周内为比赛交付一套"**感知注入 → AI 决策 → 人工审批 → 任务执行 → AI 复核 → 事件沉淀 → 二次决策引用历史**"的完整闭环演示。用 4 个版本化 fixture 场景代替真实硬件感知数据，通过前端轻量注入 UI 让评委既能看脚本演示也能自由切换场景。核心新增三张事实表（`CropSeason` / `FarmEvent` / `SensorReading`），让 AI 不再"失忆"——二次巡检能引用前一次任务执行结果。

---

## 二、Current State Analysis（现状分析）

### 已具备（可直接复用）
| 能力 | 文件 | 说明 |
|---|---|---|
| 农场/地块 CRUD | [app/api/v1/farms.py](file:///e:/GithubProgram/AgroAgentOS/app/api/v1/farms.py) | Farm + Field 静态资产 |
| AI 综合巡检 SSE 流 | [app/services/farm_agent_service.py](file:///e:/GithubProgram/AgroAgentOS/app/services/farm_agent_service.py) | `stream_inspection` 已有完整 Agent Graph 闭环 |
| 风险评估 | [app/services/farm_risk_service.py](file:///e:/GithubProgram/AgroAgentOS/app/services/farm_risk_service.py) | 2 类规则：`weather.rainstorm_drainage` + `trajectory.work_quality` |
| 提案审批 | [app/services/farm_proposal_service.py](file:///e:/GithubProgram/AgroAgentOS/app/services/farm_proposal_service.py) | pending → approved/rejected，CAS 状态机 |
| 任务状态机 | [app/services/farm_task_service.py](file:///e:/GithubProgram/AgroAgentOS/app/services/farm_task_service.py) | pending→in_progress→submitted→returned/completed/cancelled |
| AI 复核草稿 | `farm_task_service.save_verification_draft` | 仅写 `agent_verdict_json`，人工最终拍板 |
| 比赛场景开关 | [app/config.py](file:///e:/GithubProgram/AgroAgentOS/app/config.py) | `competition_demo_enabled` + `demo_scenario="rainstorm"` |
| 比赛天气 fixture | [app/data/demo_rainstorm_scenario.json](file:///e:/GithubProgram/AgroAgentOS/app/data/demo_rainstorm_scenario.json) | 阳光农场 30 亩 3 地块 + 暴雨 82mm + 1 条低质轨迹 |
| 前端驾驶舱 | [frontend-react/src/pages/FarmAgent.tsx](file:///e:/GithubProgram/AgroAgentOS/frontend-react/src/pages/FarmAgent.tsx) | 已有"比赛演示数据"开关（仅 rainstorm） |

### 核心缺口（必须补齐）
1. **无茬次维度** — AI 不知道"第几茬第几天"，决策无时间轴
2. **无事件流** — 任务完成后零沉淀，下次巡检看不到"3 天前浇过水"
3. **无感知数据存储** — fixture 只覆盖天气+轨迹，缺虫情/墒情/NDVI/长势
4. **场景单一** — 只有 rainstorm，无法展示决策覆盖面
5. **风险规则薄** — 缺虫害/缺肥/干旱规则
6. **前端联动弱** — Farms 页和 FarmAgent 页割裂，无场景选择器、无时间线视图

### 数据库迁移基线
- 最新迁移：`alembic/versions/007_add_farm_agent_workflow.py`
- 下一个迁移文件：`008_add_crop_season_and_farm_event.py`
- 数据库：默认 SQLite（`USE_SQLITE=true`），无需切换

---

## 三、Proposed Changes（变更清单）

### 后端 B1-B11

#### B1. 新增 `CropSeason` 模型 + 迁移 008
**文件**：`app/models/farm.py`（追加类） + `alembic/versions/008_add_crop_season_and_farm_event.py`
**字段**：`id, field_id(FK), crop_name, variety, season_code(2026-S1), start_date, expected_harvest, current_stage, area_mu, target_yield, status(planned/growing/harvested/aborted), created_at, updated_at`
**Field 关系**：`Field.current_season_id` 指针列（可空，迁移时回填最近 season）
**为什么**：让 AI 巡检知道"拔节期第 12 天 vs 灌浆期第 5 天"该关心不同风险。

#### B2. 新增 `FarmEvent` 模型 + 迁移 008（同迁移）
**文件**：`app/models/farm_agent.py`（追加类）
**字段**：`id, field_id(FK), season_id(FK nullable), event_type(seeding/fertilizing/irrigating/spraying/scouting/harvest/anomaly), event_time, operator, inputs_json, geo_payload_json, source(manual/task_completion/iot_trigger/agent_run), related_task_id(nullable), evidence_json, note, created_at`
**为什么**：整个联动的"中轴线"——任务完成自动写事件，下次巡检 snapshot 携带 recent_events 让 AI 有记忆。

#### B3. 新增 `SensorReading` 模型 + 迁移 009
**文件**：`app/models/farm.py`（追加类） + `alembic/versions/009_add_sensor_reading.py`
**字段**：`id, field_id(FK), sensor_type(soil_moisture/pest_count/ndvi/growth_stage/anomaly_image), value_float, value_json, unit, observed_at, source(fixture/demo_scenario/iot), scenario_id(nullable), created_at`
**索引**：`(field_id, sensor_type, observed_at desc)`
**为什么**：比赛用 fixture 注入，但模型设计要兼容未来真实 IoT，避免推倒重来。

#### B4. 新增 4 个场景 fixture 文件
**目录**：`app/data/`
- `demo_rainstorm_scenario.json`（已有，扩展）
- `demo_pest_outbreak_scenario.json`（新）
- `demo_nutrient_deficiency_scenario.json`（新）
- `demo_drought_scenario.json`（新）
**结构扩展**：每个 fixture 在现有 `farm/fields/trajectory_summaries/weather` 基础上增加 `sensor_readings` 数组（含 ndvi/soil_moisture/pest_count 等感知数据）+ `seasons` 数组（茬次信息）+ `expected_risks`（用于测试断言）。

#### B5. 新增 `app/services/demo_scenario_service.py`
**职责**：
- `load_scenario(scenario_id) -> DemoScenario`：统一加载 fixture（lru_cache）
- `inject_scenario_to_db(user_id, farm_id, scenario_id) -> InjectionReport`：把 fixture 里的 sensor_readings 写入 SensorReading 表，seasons 写入 CropSeason 表（幂等：按 `scenario_id` + `external_key` 去重）
- `list_scenarios() -> list[ScenarioMeta]`：列出所有可用场景元信息
- `validate_farm_match(farm_id, scenario)`：确保场景对应到正确的农场（比赛场景固定用"阳光农场"）
**为什么**：把场景加载逻辑从 `farm_risk_service` 解耦，便于多场景扩展。

#### B6. 扩展 `farm_risk_service.py` 风险规则
**新增 3 类规则函数**：
- `_build_pest_risk(snapshot, observed_at)` → 风险键 `pest.outbreak:{field_id}:{pest_name}`，阈值：虫情计数 ≥ 30 头/灯 或 被害率 ≥ 15%
- `_build_nutrient_risk(snapshot, observed_at)` → 风险键 `nutrient.deficiency:{field_id}:{nutrient}`，阈值：NDVI < 0.5 + 土壤氮 < 80 mg/kg
- `_build_drought_risk(snapshot, observed_at)` → 风险键 `drought.soil_moisture:{field_id}`，阈值：土壤含水量 < 25% + 7 天无有效降雨
**改造 `inspect_farm`**：在现有 weather + trajectory 风险后追加调用这 3 个规则函数
**为什么**：覆盖比赛 4 个场景，让 AI 决策有素材。

#### B7. 扩展 `farm_snapshot_service.py` 快照内容
**`FarmSnapshot` 模型新增字段**：
- `current_seasons: list[FarmSnapshotSeason]`（每个 field 当前茬次）
- `recent_events: list[FarmSnapshotEvent]`（最近 7 天事件，按 field 分组）
- `sensor_readings: list[FarmSnapshotSensor]`（每个 field 最近 24h 各类感知最新值）
**`get_snapshot` 实现**：在原有 farm/fields/trajectory 基础上追加查询这 3 类数据
**为什么**：让 Agent 拿到的 business_context 真正包含"历史 + 当前感知"。

#### B8. 改造 `farm_task_service.complete()` 自动沉淀事件
**改造点**：`complete()` 函数末尾在事务内追加：
- 写一条 `FarmEvent`（event_type 根据 `task.task_type` 映射：spray→spraying / irrigate→irrigating / fertilize→fertilizing / scout→scouting）
- `source="task_completion"`，`related_task_id=task.task_id`
- `inputs_json` 从 `task.execution_json` 提取
- `evidence_json` 包含附件 URL + 轨迹文件 ID
**为什么**：整个联动的"焊点"——任务完成 → 事件沉淀 → 下次巡检可见。

#### B9. 新增 API 路由
**`app/api/v1/farm_sensors.py`**（新文件）：
- `GET /farm-sensors/scenarios` — 列出可用比赛场景
- `POST /farm-sensors/scenarios/{scenario_id}/inject` — 注入场景感知数据到指定农场
- `GET /farms/{farm_id}/sensor-readings?field_id=&sensor_type=&days=` — 查询感知数据
**`app/api/v1/farm_events.py`**（新文件）：
- `GET /farms/{farm_id}/events?field_id=&season_id=&days=` — 查询事件流
- `POST /farms/{farm_id}/events` — 人工录入事件（巡田/打药等）
**`app/api/v1/crop_seasons.py`**（新文件）：
- `POST /fields/{field_id}/seasons` — 开启新茬次
- `GET /fields/{field_id}/seasons` — 列出茬次历史
- `PUT /seasons/{season_id}` — 更新茬次状态（人工收获/中止）
**`app/api/v1/__init__.py`**：注册上述 3 个新路由

#### B10. 扩展 `FarmInspectionRequest.demo_scenario` 枚举
**文件**：[app/schemas/farm_agent.py](file:///e:/GithubProgram/AgroAgentOS/app/schemas/farm_agent.py)
**改造**：`demo_scenario: Literal["rainstorm", "pest_outbreak", "nutrient_deficiency", "drought"] | None = None`
**配套改造 `_select_inspection_weather_provider`**：根据 scenario_id 选择对应的 WeatherProvider / SensorProvider
**为什么**：4 个场景都能通过 API 触发。

#### B11. 改造 `farm_agent_service.stream_inspection`
**改造点**：在 `inspect_farm` 之前调用 `demo_scenario_service.inject_scenario_to_db`（仅当 `demo_scenario` 非空且 `competition_demo_enabled=true`），确保数据库里有最新感知数据；之后再调 `farm_snapshot_service.get_snapshot` 拿到带 sensor_readings 的快照。
**为什么**：让"比赛演示"按钮真正把 fixture 数据落库，而不只是替换天气。

### 前端 F1-F5

#### F1. FarmAgent.tsx 场景选择器升级
**文件**：[frontend-react/src/pages/FarmAgent.tsx](file:///e:/GithubProgram/AgroAgentOS/frontend-react/src/pages/FarmAgent.tsx)
**改造**：把现有"比赛演示数据" toggle 升级为下拉选择器：
- 选项：真实数据 / 暴雨排水（rainstorm-v1）/ 虫害爆发（pest_outbreak-v1）/ 缺肥黄化（nutrient_deficiency-v1）/ 干旱胁迫（drought-v1）
- 选中场景后调用 `POST /farm-sensors/scenarios/{scenario_id}/inject` 注入数据
- 注入完成后展示"感知数据预览"卡片（每个 field 的最新 NDVI/墒情/虫情）
**新增 API 客户端**：`frontend-react/src/api/farmSensors.ts`

#### F2. Farms.tsx Field 详情页加茬次 + 时间线
**文件**：[frontend-react/src/pages/Farms.tsx](file:///e:/GithubProgram/AgroAgentOS/frontend-react/src/pages/Farms.tsx)
**新增组件**：
- `CropSeasonCard`：当前茬次信息（作物/品种/第 X 天/当前生育期/距收获 X 天）+ 历史茬次折叠
- `FarmEventTimeline`：按时间倒序展示事件流，图标按 event_type 区分（播种/施肥/灌溉/喷药/巡田/采收/异常）
- "录入事件"按钮 → 弹窗表单（类型/时间/投入品/备注）
**新增 API 客户端**：`frontend-react/src/api/farmEvents.ts` + `frontend-react/src/api/cropSeasons.ts`

#### F3. 感知数据注入面板（评委自由操作入口）
**位置**：FarmAgent.tsx 顶部控制区下方
**组件**：`SensorInjectionPanel`
- 场景下拉（同 F1）
- "高级参数微调"折叠区：暴雨量/虫口密度/NDVI 值/土壤含水量 可滑块调整
- "注入"按钮 → 调用 `POST /farm-sensors/scenarios/{scenario_id}/inject`
- 注入后显示数据预览表格
**为什么**：满足"评委自由操作"——评委可以微调参数看 AI 反应。

#### F4. Dashboard.tsx 增加农场健康分 + 近期事件
**文件**：[frontend-react/src/pages/Dashboard.tsx](file:///e:/GithubProgram/AgroAgentOS/frontend-react/src/pages/Dashboard.tsx)
**新增卡片**：
- "农场健康分"：综合最近巡检风险等级 + 待处理提案数 + 未完成任务数 + 近 7 天异常事件数，0-100 分
- "近期农事事件"：最近 5 条事件流（图标+地块+类型+时间）
- "未完成任务"：按优先级排序的待办任务列表
**为什么**：评委进入系统第一眼能看到农场整体态势。

#### F5. FarmAgent.tsx 任务完成后自动刷新事件流
**改造点**：`completeFarmTask` 成功回调中，除了 `refreshWorkflow()` 还要 `invalidateQueries(["farm-events", farmId])`
**为什么**：让"任务完成 → 事件出现"的联动在 UI 上即时可见。

### 数据 D1-D2

#### D1. 4 个场景 fixture 文件内容
见下方"四、比赛场景设计"。

#### D2. 场景说明文档
**文件**：`docs/competition_scenarios.md`
**内容**：每个场景的背景故事、感知数据、期望风险、期望提案、演示要点。

### 文档 DOC1-DOC2

#### DOC1. 演示剧本
**文件**：`docs/competition_demo_script.md`
**内容**：见下方"五、演示剧本"。

#### DOC2. 架构说明
**文件**：`docs/farm_cockpit_architecture.md`
**内容**：联动架构图、数据流、模型关系图（用于评委技术答疑）。

### 测试 T1-T4

#### T1. `tests/services/test_farm_risk_rules.py`
覆盖 4 类风险规则的阈值边界：
- 暴雨 50/80mm 临界值
- 虫情 30/15% 阈值
- NDVI 0.5 + 土壤氮 80 阈值
- 土壤含水量 25% + 7 天无雨阈值

#### T2. `tests/services/test_demo_scenario_service.py`
- 4 个 fixture 都能正确加载
- `inject_scenario_to_db` 幂等性（重复注入不重复创建）
- 场景对应的 farm_id 校验

#### T3. `tests/services/test_farm_event_flow.py`
- 任务 complete → FarmEvent 自动写入
- snapshot.recent_events 包含该事件
- 二次巡检 business_context 包含该事件

#### T4. `tests/services/test_crop_season_lifecycle.py`
- 创建 season → Field.current_season_id 更新
- 结束 season → status=harvested，current_season_id 清空

---

## 四、比赛场景设计（4 个）

所有场景固定使用 **阳光农场**（南京江宁区，30 亩，3 地块：A1 水稻 / A2 玉米 / A3 大豆），不同场景是**同一农场不同时间点**，便于展示"AI 记忆"能力。

### 场景 1: rainstorm-v1（已有，增强）
| 字段 | 值 |
|---|---|
| 时间点 | 2026-07-18 |
| 触发条件 | `demo_scenario="rainstorm"` |
| 天气 | 24h 降雨 82mm |
| 轨迹 | A1 低质耕作（depth_std=7.5, 覆盖率 42%） |
| **新增感知** | A1 土壤含水量 95%（饱和）+ A2/A3 正常 |
| 期望风险 | `weather.rainstorm_drainage`(critical) + `trajectory.work_quality:A1`(medium) |
| 期望提案 | 清理 A1 排水沟 + 复核 A1 耕深标定 |
| 演示要点 | 展示"气象+轨迹+墒情"三源融合风险识别 |

### 场景 2: pest_outbreak-v1（新）
| 字段 | 值 |
|---|---|
| 时间点 | 2026-07-25（rainstorm 后 7 天） |
| 触发条件 | `demo_scenario="pest_outbreak"` |
| 天气 | 晴，气温 28-32℃（适宜虫害繁殖） |
| 感知数据 | A2 玉米虫情测报灯捕获草地贪夜蛾 35 头/灯；叶片图像识别被害率 18%；A2 NDVI 0.62（轻度下降） |
| 期望风险 | `pest.outbreak:A2:草地贪夜蛾`(high) |
| 期望提案 | A2 定点施药（氯虫苯甲酰胺）+ 设置诱捕器 + 7 天后复查 |
| 演示要点 | AI 引用"7 天前刚清理过 A1 排水沟"做对比，展示记忆能力 |

### 场景 3: nutrient_deficiency-v1（新）
| 字段 | 值 |
|---|---|
| 时间点 | 2026-08-02（pest_outbreak 后 8 天） |
| 触发条件 | `demo_scenario="nutrient_deficiency"` |
| 天气 | 多云，气温 26-30℃ |
| 感知数据 | A3 大豆 NDVI 0.42（偏低）；土壤速效氮 65 mg/kg（缺氮）；叶片黄化图像识别；A1/A2 正常 |
| 期望风险 | `nutrient.deficiency:A3:氮`(medium) |
| 期望提案 | A3 追施尿素 5kg/亩 + 喷施叶面肥（0.2% 磷酸二氢钾）+ 5 天后复查 NDVI |
| 演示要点 | 多光谱 NDVI + 土壤检测 + 视觉识别三源融合 |

### 场景 4: drought-v1（新）
| 字段 | 值 |
|---|---|
| 时间点 | 2026-08-12（nutrient_deficiency 后 10 天） |
| 触发条件 | `demo_scenario="drought"` |
| 天气 | 连续 12 天无雨，气温 33-36℃ |
| 感知数据 | A1 水稻土壤含水量 22%（严重干旱）；A1 田面无水层；作物蒸散量 6.5mm/天；A2/A3 轻度缺水 |
| 期望风险 | `drought.soil_moisture:A1`(high) |
| 期望提案 | A1 灌溉 30m³/亩 + 调整水层管理（保持 3-5cm 水层）+ 3 天后复查墒情 |
| 演示要点 | AI 引用"20 天前 rainstorm 场景下 A1 排水沟已清理"做对比，展示长期记忆 |

---

## 五、演示剧本（10 步完整流程）

> 文件：`docs/competition_demo_script.md`

### 第一幕：场景导入（90 秒）
1. 登录系统，进入 Dashboard，看到"阳光农场"健康分 85
2. 点击进入"AI 农场驾驶舱"，选择"阳光农场"
3. 切换场景为"暴雨排水（rainstorm-v1）"，点击"注入感知数据"
4. 系统展示 A1 地块最新感知：降雨 82mm + 土壤含水量 95% + 轨迹质量异常

### 第二幕：AI 决策（2 分钟）
5. 点击"开始 AI 综合巡检"，观看 SSE 流式输出：
   - `context_loaded`：业务上下文已加载（含 recent_events）
   - `plan`：执行计划（拉天气 + 拉轨迹 + 拉感知 + 评估风险）
   - `step_complete`：每个工具调用结果
   - `proposal_created`：生成 2 个提案
6. 在"待确认行动提案"中查看提案详情（含证据链 evidence + 建议 actions）

### 第三幕：人工审批与执行（90 秒）
7. 审批通过"清理 A1 排水沟"提案 → 自动生成 FarmTask
8. 在 FarmTaskBoard 中：start → submit（附"排水沟已清理"备注 + 现场照片 URL）
9. 点击"AI 复核" → AI 生成 verdict=pass → 人工 complete

### 第四幕：闭环沉淀（60 秒）
10. 切换到"农场管理"页 → A1 地块详情 → 看到"农事时间线"自动出现一条"排水沟清理"事件
11. 切换场景为"虫害爆发（pest_outbreak-v1）" → 再次巡检
12. **关键时刻**：AI 在新提案的 evidence 中引用"7 天前 A1 排水沟已清理，A1 当前无积水风险，重点关注 A2 虫害"

### 评委自由操作（开放）
- 评委可在 F3 面板微调参数（如把虫口密度从 35 改为 50）看 AI 反应
- 评委可切换其他 2 个场景验证决策覆盖面
- 评委可在 Farms 页人工录入事件，再巡检验证 AI 是否引用

---

## 六、任务分解与时间安排（3-4 周）

### Week 1：数据底座
| 任务 | 文件 | 估时 |
|---|---|---|
| B1 CropSeason 模型 + 迁移 008 | `app/models/farm.py`, `alembic/versions/008_*` | 0.5 天 |
| B2 FarmEvent 模型 + 迁移 008 | `app/models/farm_agent.py` | 0.5 天 |
| B3 SensorReading 模型 + 迁移 009 | `app/models/farm.py`, `alembic/versions/009_*` | 0.5 天 |
| B5 demo_scenario_service | `app/services/demo_scenario_service.py` | 1 天 |
| D1 4 个场景 fixture | `app/data/demo_*.json` | 1.5 天 |
| T2 场景加载测试 | `tests/services/test_demo_scenario_service.py` | 0.5 天 |
| T4 茬次生命周期测试 | `tests/services/test_crop_season_lifecycle.py` | 0.5 天 |

### Week 2：业务逻辑
| 任务 | 文件 | 估时 |
|---|---|---|
| B6 风险规则扩展（3 类） | `app/services/farm_risk_service.py` | 1.5 天 |
| B7 snapshot 扩展 | `app/services/farm_snapshot_service.py` | 1 天 |
| B8 任务完成沉淀 | `app/services/farm_task_service.py` | 0.5 天 |
| B11 stream_inspection 改造 | `app/services/farm_agent_service.py` | 0.5 天 |
| B10 demo_scenario 枚举扩展 | `app/schemas/farm_agent.py` | 0.5 天 |
| T1 风险规则测试 | `tests/services/test_farm_risk_rules.py` | 1 天 |
| T3 事件流测试 | `tests/services/test_farm_event_flow.py` | 1 天 |

### Week 3：前端联动
| 任务 | 文件 | 估时 |
|---|---|---|
| B9 API 路由（sensors/events/seasons） | `app/api/v1/farm_*.py` | 1 天 |
| F1 FarmAgent 场景选择器 | `frontend-react/src/pages/FarmAgent.tsx` | 1 天 |
| F3 感知注入面板 | `frontend-react/src/components/farm-agent/SensorInjectionPanel.tsx` | 1.5 天 |
| F2 Farms 茬次+时间线 | `frontend-react/src/pages/Farms.tsx` + 组件 | 2 天 |
| F4 Dashboard 健康分 | `frontend-react/src/pages/Dashboard.tsx` | 1 天 |
| F5 任务完成刷新事件 | `frontend-react/src/pages/FarmAgent.tsx` | 0.5 天 |

### Week 4：演示与测试
| 任务 | 文件 | 估时 |
|---|---|---|
| DOC1 演示剧本 | `docs/competition_demo_script.md` | 1 天 |
| DOC2 架构说明 | `docs/farm_cockpit_architecture.md` | 1 天 |
| 端到端走通 4 个场景 | - | 2 天 |
| Bug 修复与优化 | - | 2 天 |

---

## 七、Assumptions & Decisions（假设与决策）

### 关键决策
1. **数据库**：继续用 SQLite，不切 MySQL（比赛演示单机够用）
2. **感知数据来源**：全部用 fixture 注入，不接真实卫星/IoT API（用户明确说无硬件）
3. **场景固定农场**：4 个场景都用"阳光农场"，是同一农场不同时间点（展示 AI 记忆能力）
4. **不做处方图空间化**：FarmTask 文字 instructions 顶一阵，WorkOrder 推迟到 V2
5. **demo_scenario 枚举扩展**：从 1 个扩展到 4 个，向后兼容
6. **任务完成自动写事件**：在 `farm_task_service.complete()` 事务内追加，保证原子性
7. **幂等注入**：`inject_scenario_to_db` 按 `(scenario_id, external_key)` 去重，重复注入不报错

### 关键假设
1. 评委允许在比赛机上切换场景（前端 UI 可操作）
2. 比赛环境能跑 DashScope API（`DASHSCOPE_API_KEY` 可用）
3. 现有 Agent Graph 的 recursion_limit 足够支撑新增感知数据查询步骤（如不够再调 `agent_max_steps`）
4. SQLite 单机并发足够（比赛演示无高并发）

### 取舍（砍掉的内容）
- ❌ 卫星 NDVI 真实接入（Sentinel Hub）→ 用 fixture 模拟
- ❌ IoT 设备协议适配（MQTT/CoAP）→ 用 fixture 模拟
- ❌ WorkOrder 处方图空间化（GeoJSON 多边形变量施药）→ 用 FarmTask 文字 instructions
- ❌ 多季节产量分析、经营报告 → 推迟到 V3
- ❌ MCP 工具自动下发无人机/水阀任务 → 推迟到 V3

---

## 八、Verification（验证步骤）

### 单元测试
```bash
pytest tests/services/test_farm_risk_rules.py
pytest tests/services/test_demo_scenario_service.py
pytest tests/services/test_farm_event_flow.py
pytest tests/services/test_crop_season_lifecycle.py
```

### 端到端验证（按演示剧本）
1. 启动后端：`uvicorn app.main:app --reload --port 9800`
2. 启动前端：`cd frontend-react && npm run dev`
3. 在 .env 设置 `COMPETITION_DEMO_ENABLED=true`
4. 按演示剧本 10 步走通 rainstorm 场景
5. 切换 pest_outbreak 场景，验证 AI 在 evidence 中引用 rainstorm 事件
6. 切换 nutrient_deficiency + drought 场景，验证 4 类风险规则都能触发
7. 在 Farms 页验证事件时间线自动更新

### 验收标准
- [ ] 4 个场景 fixture 都能通过 `POST /farm-sensors/scenarios/{id}/inject` 注入成功
- [ ] 4 类风险规则在对应场景下都能生成正确风险
- [ ] 任务 complete 后 FarmEvent 自动写入，能在 `GET /farms/{id}/events` 查到
- [ ] 二次巡检的 `business_context.recent_events` 包含上一次任务事件
- [ ] AI 在 pest_outbreak 场景的 evidence 中能引用 rainstorm 场景的事件
- [ ] 前端场景选择器切换 4 个场景都能正常注入并预览感知数据
- [ ] Dashboard 健康分能根据风险/提案/任务/事件动态变化
- [ ] 所有测试通过

### 风险与回退方案
| 风险 | 回退方案 |
|---|---|
| Agent Graph 步骤数不够 | 调高 `agent_max_steps` 从 5 到 8 |
| DashScope API 限流 | 切到 DeepSeek 模型（项目已支持） |
| 4 个场景开发不完 | 优先 rainstorm + pest_outbreak，后两个用相同 fixture 改参数 |
| 前端时间不够 | F4 Dashboard 健康分可砍，F2 时间线必须保留（演示核心） |

---

## 九、文件清单（一图总览）

```
新增文件：
├── app/data/demo_pest_outbreak_scenario.json
├── app/data/demo_nutrient_deficiency_scenario.json
├── app/data/demo_drought_scenario.json
├── app/services/demo_scenario_service.py
├── app/api/v1/farm_sensors.py
├── app/api/v1/farm_events.py
├── app/api/v1/crop_seasons.py
├── alembic/versions/008_add_crop_season_and_farm_event.py
├── alembic/versions/009_add_sensor_reading.py
├── frontend-react/src/api/farmSensors.ts
├── frontend-react/src/api/farmEvents.ts
├── frontend-react/src/api/cropSeasons.ts
├── frontend-react/src/components/farm-agent/SensorInjectionPanel.tsx
├── frontend-react/src/components/farms/CropSeasonCard.tsx
├── frontend-react/src/components/farms/FarmEventTimeline.tsx
├── frontend-react/src/components/farms/EventEntryModal.tsx
├── tests/services/test_farm_risk_rules.py
├── tests/services/test_demo_scenario_service.py
├── tests/services/test_farm_event_flow.py
├── tests/services/test_crop_season_lifecycle.py
├── docs/competition_demo_script.md
├── docs/competition_scenarios.md
└── docs/farm_cockpit_architecture.md

修改文件：
├── app/models/farm.py（追加 CropSeason, SensorReading 类 + Field.current_season_id）
├── app/models/farm_agent.py（追加 FarmEvent 类）
├── app/schemas/farm_agent.py（扩展 demo_scenario 枚举 + 新增 schemas）
├── app/services/farm_risk_service.py（追加 3 类风险规则）
├── app/services/farm_snapshot_service.py（扩展 snapshot 字段）
├── app/services/farm_task_service.py（complete 自动写事件）
├── app/services/farm_agent_service.py（stream_inspection 注入场景）
├── app/api/v1/__init__.py（注册 3 个新路由）
├── app/data/demo_rainstorm_scenario.json（追加 sensor_readings + seasons）
├── frontend-react/src/pages/FarmAgent.tsx（场景选择器 + 注入面板）
├── frontend-react/src/pages/Farms.tsx（茬次卡片 + 时间线）
├── frontend-react/src/pages/Dashboard.tsx（健康分 + 近期事件）
└── .env（COMPETITION_DEMO_ENABLED=true）
```
