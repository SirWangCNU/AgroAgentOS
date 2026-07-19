# 比赛演示完整执行计划 — 农场管理 × AI 驾驶舱联动

> 适用场景：3-4 周比赛窗口、无硬件设备、用 fixture 文件模拟感知数据输入
> 计划基线：基于已完成的数据底座（B1/B2/B3/B5/D1），续作业务逻辑 / API / 前端 / 文档
> 文件命名约定：本计划用 `B` 前缀表示后端任务、`F` 前缀表示前端任务、`T` 前缀表示测试、`DOC` 前缀表示文档

---

## 一、Summary（执行摘要）

本计划在已完成的"数据底座"之上，把 AgroAgentOS 打造成可在比赛现场演示的**感知-认知-决策-执行-反馈**闭环平台。核心是把 4 个时间点递进的 fixture 场景，通过 `demo_scenario_service.inject_scenario_to_db` 注入到 `sensor_readings` / `crop_seasons` 表，由扩展后的 `farm_risk_service` 生成确定性风险，由 `farm_snapshot_service` 把感知+事件带入 Agent 上下文，由 `farm_task_service.complete` 在任务完成时自动写 `FarmEvent` 形成"记忆"。前端在 FarmAgent 页面增加场景选择器与感知面板，在 Farms 页面增加茬次卡片与事件时间线，在 Dashboard 增加农场健康分。最终演示 10 步剧本，覆盖从暴雨内涝到虫害爆发到缺肥黄化到干旱胁迫的完整季节演化。

---

## 二、Current State Analysis（当前实施状态）

### 2.1 已完成（Week 1 — 数据底座）

| 任务 | 文件 | 状态 |
|------|------|------|
| B1 CropSeason + SensorReading ORM | [app/models/farm.py](file:///e:/GithubProgram/AgroAgentOS/app/models/farm.py) | ✅ |
| B2 FarmEvent ORM | [app/models/farm_agent.py](file:///e:/GithubProgram/AgroAgentOS/app/models/farm_agent.py#L169-L229) | ✅ |
| B3 迁移 008 + 009 | [alembic/versions/008_add_crop_season_and_farm_event.py](file:///e:/GithubProgram/AgroAgentOS/alembic/versions/008_add_crop_season_and_farm_event.py), [alembic/versions/009_add_sensor_reading.py](file:///e:/GithubProgram/AgroAgentOS/alembic/versions/009_add_sensor_reading.py) | ✅ |
| B5 demo_scenario_service | [app/services/demo_scenario_service.py](file:///e:/GithubProgram/AgroAgentOS/app/services/demo_scenario_service.py) | ✅ 394 行完整实现 |
| D1 4 个场景 fixture | [app/data/demo_rainstorm_scenario.json](file:///e:/GithubProgram/AgroAgentOS/app/data/demo_rainstorm_scenario.json) 等 4 个 | ✅ |

**B5 已实现契约**：
- `load_scenario(scenario_id) -> DemoScenario`（lru_cache）
- `list_scenarios() -> list[ScenarioMeta]`
- `inject_scenario_to_db(*, user_id, farm_id, scenario_id) -> InjectionReport`（幂等，含 Field.current_season_id 同步）

### 2.2 待完成（Week 2-4 — 业务逻辑 / API / 前端 / 文档）

| 任务 | 当前痛点 | 目标 |
|------|----------|------|
| B6 风险规则扩展 | [farm_risk_service.py:276-348](file:///e:/GithubProgram/AgroAgentOS/app/services/farm_risk_service.py#L276-L348) `inspect_farm` 只生成 weather + trajectory 风险 | 新增 pest/nutrient/drought 三类确定性规则 |
| B7 snapshot 扩展 | [farm_snapshot_service.py:61-71](file:///e:/GithubProgram/AgroAgentOS/app/services/farm_snapshot_service.py#L61-L71) FarmSnapshot 缺 sensor_readings 和 recent_events | 新增两个字段并查询 |
| B8 任务完成写事件 | [farm_task_service.py:385-405](file:///e:/GithubProgram/AgroAgentOS/app/services/farm_task_service.py#L385-L405) `complete()` 仅状态转换 | completed 时插入 FarmEvent |
| B9 API 路由 | [farm_agent.py](file:///e:/GithubProgram/AgroAgentOS/app/api/v1/farm_agent.py) 缺 scenarios/sensors/events/seasons | 新增 5 个 endpoint |
| B10+B11 枚举扩展+注入 | [farm_agent.py schema:119-125](file:///e:/GithubProgram/AgroAgentOS/app/schemas/farm_agent.py#L119-L125) `demo_scenario: Literal["rainstorm"]` | 扩展 4 个值 + stream_inspection 内注入 |
| F1+F3 场景选择器+感知面板 | [FarmAgent.tsx:77](file:///e:/GithubProgram/AgroAgentOS/frontend-react/src/pages/FarmAgent.tsx#L77) `demoMode` 只是布尔开关 | 改为下拉选择 + 注入按钮 + 感知面板 |
| F2 茬次卡片+时间线 | [Farms.tsx](file:///e:/GithubProgram/AgroAgentOS/frontend-react/src/pages/Farms.tsx) 仅展示农场/地块/轨迹 | Field 卡片新增茬次 + 事件时间线 |
| F4+F5 Dashboard 健康分+刷新 | [Dashboard.tsx](file:///e:/GithubProgram/AgroAgentOS/frontend-react/src/pages/Dashboard.tsx) 无健康分卡片 | 新增 health_score 卡片 + 任务完成刷新事件 |
| T1+T2+T3+T4 测试 | tests/services/ 无相关测试 | 4 类测试覆盖 |
| DOC1+DOC2 文档 | 无演示剧本与架构说明 | 写 2 篇 markdown |

---

## 三、4 个比赛场景设计（同农场不同时间点）

> 同一农场（江苏南京试验农场，3 个地块 A1/A2/A3），4 个时间点递进，展示 AI 记忆能力

| scenario_id | 日期 | 地块 | 主要作物 | 生育期 | 关键感知 | 期望风险 |
|-------------|------|------|---------|--------|----------|----------|
| `rainstorm` | 2026-07-18 | A1 | 水稻 | 分蘖期 | 土壤含水量 95%、降雨 158mm | `weather.rainstorm_drainage` high |
| `pest_outbreak` | 2026-07-25 | A2 | 玉米 | 拔节期 | 草地贪夜蛾 35 头/灯、被害率 18%、NDVI 0.62 | `pest.outbreak` high |
| `nutrient_deficiency` | 2026-08-02 | A3 | 大豆 | 开花期 | NDVI 0.42、速效氮 65 mg/kg、叶片黄化 35% | `nutrient.deficiency` medium |
| `drought` | 2026-08-12 | A1 | 水稻 | 抽穗期 | 土壤含水量 22%、12 天无雨、ETo 6.5 mm/天 | `drought.stress` high |

**记忆联动示例**：演示 `drought` 时，AI 在 snapshot 中看到 `recent_events` 含 25 天前的排水作业（rainstorm→drainage task completion），可在报告中引用"7 月底刚排过水，本轮转旱需注意水分管理切换"。

---

## 四、Proposed Changes（按周分解的具体改动）

### Week 2 — 业务逻辑层（B6/B7/B8/B10/B11）

#### B6 扩展 farm_risk_service（pest/nutrient/drought 风险规则）

**文件**：[app/services/farm_risk_service.py](file:///e:/GithubProgram/AgroAgentOS/app/services/farm_risk_service.py)

**新增内容**：
1. 新增 `_build_pest_risk(session, field, observed_at)` 函数：
   - 查询 `SensorReading` where `sensor_type='pest_count'` order by `observed_at desc limit 1`
   - 阈值：`value_json.count_per_light >= 30` → high；`>=15` → medium
   - 同时查询 `sensor_type='anomaly_image'` 的 `value_json.affected_rate`，作为辅助证据
   - 返回 `Risk` 对象（risk_key=`pest.outbreak`，evidence 含 measured 证据）

2. 新增 `_build_nutrient_risk(session, field, observed_at)` 函数：
   - 查询 `sensor_type='ndvi'` 最新值，阈值 `< 0.5` 触发
   - 查询 `sensor_type='soil_nitrogen'`，阈值 `< 80 mg/kg` 加重严重度
   - 返回 `Risk` 对象（risk_key=`nutrient.deficiency`）

3. 新增 `_build_drought_risk(session, field, observed_at)` 函数：
   - 查询 `sensor_type='soil_moisture'` 最新值，阈值 `< 30%` 触发
   - 读取 `DemoScenarioWeather.consecutive_dry_days` 和 `eto_mm_per_day` 作为辅助（通过 scenario_id 关联）
   - 返回 `Risk` 对象（risk_key=`drought.stress`）

4. 改造 `inspect_farm(snapshot, *, weather_provider, days)` 函数：
   - 在生成 weather/trajectory 风险后，新增"遍历 fields，对每个 field 调用三个新规则函数"
   - 把 session 通过参数传入（或在函数内开新会话）
   - 把生成的新风险 append 到 `risks` 列表

**改动要点**：
- 风险判定保持确定性（不调用 LLM），符合 `inspect_farm` 现有设计
- 证据 fact_kind 用 `measured`，对应 SensorReading
- 阈值常量集中在文件顶部 `_PEST_THRESHOLD_HIGH = 30` 等

**预计工作量**：1 天

---

#### B7 扩展 farm_snapshot_service（sensor_readings + recent_events）

**文件**：[app/services/farm_snapshot_service.py](file:///e:/GithubProgram/AgroAgentOS/app/services/farm_snapshot_service.py)

**新增内容**：
1. 新增 Pydantic 模型：
   ```python
   class FarmSnapshotSensorReading(BaseModel):
       id: int
       field_id: int
       sensor_type: str
       value_float: float | None
       value: dict[str, Any]
       unit: str
       observed_at: datetime
       source: str
       scenario_id: str | None
       note: str
       model_config = ConfigDict(from_attributes=True)

   class FarmSnapshotEvent(BaseModel):
       id: int
       field_id: int
       season_id: int | None
       event_type: str
       event_time: datetime
       operator: str
       inputs: list[Any]
       source: str
       related_task_id: str | None
       note: str
       model_config = ConfigDict(from_attributes=True)
   ```

2. 在 `FarmSnapshot` 类新增字段：
   ```python
   sensor_readings: list[FarmSnapshotSensorReading] = PydanticField(default_factory=list)
   recent_events: list[FarmSnapshotEvent] = PydanticField(default_factory=list)
   ```

3. 在 `get_snapshot(farm_id, user_id)` 函数内新增查询：
   - 查询 `SensorReading` where `field_id IN (field_ids)` AND `observed_at >= now - 7 days`，order by `observed_at desc`，limit 50（每地块约 5 条）
   - 查询 `FarmEvent` where `field_id IN (field_ids)` AND `event_time >= now - 14 days`，order by `event_time desc`，limit 20

4. 在 `_build_data_gaps` 内补充：
   - 若某 field 在最近 7 天无 sensor_readings，append `f"field:{field.id}:sensor_data_stale"`

**改动要点**：
- 不修改 `FarmSnapshotField` 已有字段，避免破坏前端契约
- `value` property 复用 `SensorReading.value` 的 json.loads 逻辑
- 查询在原有 `with sqlite_manager.session() as session:` 内完成，复用一次会话

**预计工作量**：0.5 天

---

#### B8 改造 farm_task_service.complete（自动写 FarmEvent）

**文件**：[app/services/farm_task_service.py](file:///e:/GithubProgram/AgroAgentOS/app/services/farm_task_service.py)

**改动**：
1. 在文件顶部 import：`from app.models.farm_agent import FarmEvent` 和 `from datetime import datetime, timezone`
2. 在 `_transition` 函数内（或在 `complete` 函数调用 `_transition` 之前），增加 `target_status == "completed"` 分支：
   ```python
   if target_status == "completed" and task.field_id is not None:
       event = FarmEvent(
           field_id=task.field_id,
           season_id=_resolve_current_season_id(session, task.field_id),
           event_type=_map_task_type_to_event_type(task.task_type),
           event_time=datetime.now(timezone.utc),
           operator=f"user:{user_id}",
           source="task_completion",
           related_task_id=task.task_id,
           note=note,
       )
       event.set_inputs(_extract_inputs_from_execution(task.execution))
       session.add(event)
   ```

3. 新增辅助函数：
   - `_map_task_type_to_event_type(task_type: str) -> str`：spraying/fertilizing/irrigating/scouting/harvest/seeding
   - `_resolve_current_season_id(session, field_id) -> int | None`：查 `Field.current_season_id`
   - `_extract_inputs_from_execution(execution: dict) -> list[dict]`：从 execution_json 提取投入品清单

4. 验证幂等：`uq_event_task_type (related_task_id, event_type)` 约束保证重复 complete 不创建重复事件

**改动要点**：
- 仅 `complete` 触发，`return` / `cancel` 不写事件
- 在同一事务内完成，保证原子性
- 兼容 `field_id is None` 的任务（跳过事件写入）

**预计工作量**：0.5 天

---

#### B10+B11 扩展 demo_scenario 枚举 + stream_inspection 注入场景

**文件 1**：[app/schemas/farm_agent.py:119-125](file:///e:/GithubProgram/AgroAgentOS/app/schemas/farm_agent.py#L119-L125)

**改动**：
```python
DemoScenario = Literal["rainstorm", "pest_outbreak", "nutrient_deficiency", "drought"]

class FarmInspectionRequest(BaseModel):
    farm_id: int = Field(..., gt=0)
    objective: str = Field(default="请对当前农场执行综合巡检", min_length=1)
    demo_scenario: DemoScenario | None = None
    inject_scenario: bool = Field(default=True)  # 是否在巡检前注入感知数据
```

**文件 2**：[app/services/farm_agent_service.py](file:///e:/GithubProgram/AgroAgentOS/app/services/farm_agent_service.py) `stream_inspection` 函数

**改动**：
- 在 `stream_inspection(user_id, request)` 顶部，若 `request.demo_scenario is not None and request.inject_scenario`：
  ```python
  from app.services import demo_scenario_service
  injection_report = demo_scenario_service.inject_scenario_to_db(
      user_id=user_id,
      farm_id=request.farm_id,
      scenario_id=request.demo_scenario,
  )
  yield {
      "type": "scenario_injected",
      "data": injection_report.model_dump(mode="json"),
      "message": f"已注入场景 {request.demo_scenario}: 新增感知 {injection_report.created_sensors} 条",
  }
  ```
- 然后继续原有 `get_snapshot` → `inspect_farm` → `propose_action` 流程

**改动要点**：
- 注入在 stream_inspection 内执行，前端通过 SSE 看到 `scenario_injected` 事件
- 注入后再 get_snapshot，确保 snapshot 包含最新 sensor_readings
- `inject_scenario=False` 用于"已注入过的场景只重新巡检"

**预计工作量**：0.5 天

---

### Week 2 测试（T1+T3）

#### T1 风险规则测试

**文件**：`tests/services/test_farm_risk_service_pest_nutrient_drought.py`（新建）

**测试用例**：
- `test_pest_outbreak_high_risk`：注入 35 头/灯 → 期望 `pest.outbreak` high
- `test_pest_outbreak_medium_risk`：注入 20 头/灯 → 期望 medium
- `test_nutrient_deficiency_triggered`：NDVI 0.42 + 速效氮 65 → 期望 `nutrient.deficiency` medium
- `test_drought_stress_triggered`：土壤含水量 22% → 期望 `drought.stress` high
- `test_no_risk_when_sensors_normal`：注入正常值 → 期望不触发风险

#### T3 事件流测试

**文件**：`tests/services/test_farm_task_event_flow.py`（新建）

**测试用例**：
- `test_complete_task_writes_farm_event`：完成任务 → FarmEvent 表新增 1 条 source=task_completion
- `test_event_idempotent_on_retry_complete`：重复 complete 同一任务 → FarmEvent 不重复
- `test_event_type_mapping`：spraying 任务 → event_type=spraying
- `test_event_carries_inputs_from_execution`：execution 含投入品 → event.inputs 反映

#### T2+T4 场景加载与茬次生命周期测试

**文件**：`tests/services/test_demo_scenario_service.py`（新建）和 `tests/services/test_crop_season_lifecycle.py`（新建）

**测试用例**：
- `test_load_scenario_returns_validated_model`：4 个 scenario_id 都能加载
- `test_list_scenarios_returns_4_metas`：list_scenarios 返回 4 条
- `test_inject_is_idempotent`：连续两次注入同一场景 → 第二次 created_sensors=0, skipped_sensors=N
- `test_inject_syncs_field_current_season_id`：注入后 Field.current_season_id 非空
- `test_inject_updates_season_stage`：第二次注入不同 current_stage → CropSeason.current_stage 更新

**预计工作量（T1+T2+T3+T4）**：1.5 天

---

### Week 3 — API 层 + 前端联动

#### B9 新增 API 路由（5 个 endpoint）

**文件**：[app/api/v1/farm_agent.py](file:///e:/GithubProgram/AgroAgentOS/app/api/v1/farm_agent.py) 追加路由

**新增 endpoint**：

1. `GET /farm-agent/scenarios`
   - 调用 `demo_scenario_service.list_scenarios()`
   - 返回 `ApiResponse[list[ScenarioMeta]]`

2. `POST /farm-agent/scenarios/{scenario_id}/inject`
   - Body: `{ "farm_id": int }`
   - 调用 `inject_scenario_to_db(user_id, farm_id, scenario_id)`
   - 返回 `ApiResponse[InjectionReport]`

3. `GET /farm-agent/sensors`
   - Query: `farm_id`, `field_id?`, `sensor_type?`, `days=7`
   - 查询 SensorReading 表
   - 返回 `ApiResponse[list[FarmSnapshotSensorReading]]`

4. `GET /farm-agent/events`
   - Query: `farm_id`, `field_id?`, `days=14`
   - 查询 FarmEvent 表
   - 返回 `ApiResponse[list[FarmSnapshotEvent]]`

5. `GET /farm-agent/seasons`
   - Query: `farm_id`, `field_id?`, `status?`
   - 查询 CropSeason 表
   - 返回 `ApiResponse[list[CropSeasonResponse]]`（需新建 schema）

**改动要点**：
- 5 个 endpoint 都加 `Depends(get_current_user)` 鉴权
- 都通过 `farm_run_query_service.require_owned_farm` 校验农场所有权
- 在 [app/schemas/farm_agent.py](file:///e:/GithubProgram/AgroAgentOS/app/schemas/farm_agent.py) 新增 `CropSeasonResponse`、`SensorReadingResponse`、`FarmEventResponse` 三个 Pydantic 模型

**预计工作量**：1 天

---

#### F1+F3 FarmAgent 场景选择器 + 感知注入面板

**文件**：[frontend-react/src/pages/FarmAgent.tsx](file:///e:/GithubProgram/AgroAgentOS/frontend-react/src/pages/FarmAgent.tsx)

**改动**：
1. 把 `demoMode: boolean` 改为 `selectedScenario: string | null`：
   ```tsx
   const [selectedScenario, setSelectedScenario] = useState<string | null>(null);
   const { data: scenarios = [] } = useQuery({
     queryKey: ["farm-agent-scenarios"],
     queryFn: listFarmScenarios,
   });
   ```

2. UI 改为下拉选择 + 注入按钮：
   ```tsx
   <select value={selectedScenario ?? ""} onChange={(e) => setSelectedScenario(e.target.value || null)}>
     <option value="">真实数据</option>
     {scenarios.map((s) => <option key={s.scenario_id} value={s.scenario_id}>{s.label}</option>)}
   </select>
   {selectedScenario && (
     <button onClick={() => injectMutation.mutate({ scenario_id: selectedScenario, farm_id: farmId })}>
       注入感知数据
     </button>
   )}
   ```

3. 在 inspect 函数内把 `demo_scenario: "rainstorm"` 改为 `demo_scenario: selectedScenario ?? undefined`

4. 新增感知注入面板组件 `<SensorPanel farmId={farmId} />`（在 FarmRiskCard 上方）：
   - 查询 `GET /farm-agent/sensors?farm_id=X&days=7`
   - 按地块分组展示最新 5 条 sensor_readings（值 + 单位 + observed_at + sensor_type 图标）
   - 暖色杂志编辑风格，无截断

5. 新增事件时间线组件 `<FarmEventTimeline farmId={farmId} />`（在 FarmTaskBoard 下方）：
   - 查询 `GET /farm-agent/events?farm_id=X&days=14`
   - 时间倒序展示，每条事件显示 event_type / event_time / operator / note
   - 任务完成事件用绿色标记，人工录入用灰色，agent_run 用紫色

**新增 API 文件**：[frontend-react/src/api/farmAgent.ts](file:///e:/GithubProgram/AgroAgentOS/frontend-react/src/api/farmAgent.ts) 追加：
- `listFarmScenarios(): Promise<ScenarioMeta[]>`
- `injectFarmScenario(scenarioId: string, farmId: number): Promise<InjectionReport>`
- `listFarmSensors(params): Promise<SensorReading[]>`
- `listFarmEvents(params): Promise<FarmEvent[]>`
- `listFarmSeasons(params): Promise<CropSeason[]>`

**新增组件文件**：
- `frontend-react/src/components/farm-agent/SensorPanel.tsx`
- `frontend-react/src/components/farm-agent/FarmEventTimeline.tsx`

**预计工作量**：1.5 天

---

#### F2 Farms 茬次卡片 + 时间线

**文件**：[frontend-react/src/pages/Farms.tsx](file:///e:/GithubProgram/AgroAgentOS/frontend-react/src/pages/Farms.tsx)

**改动**：
1. 在 Field 卡片（已有 current_crop/growth_stage 展示）下方新增茬次卡片：
   - 查询 `GET /farm-agent/seasons?farm_id=X&field_id=Y`
   - 显示当前茬次：crop_name + variety + season_code + current_stage + start_date + expected_harvest + target_yield + area_mu
   - 用进度条表示生育期进度（start_date → expected_harvest）

2. 在茬次卡片下方新增事件时间线：
   - 查询 `GET /farm-agent/events?farm_id=X&field_id=Y&days=30`
   - 紧凑垂直时间线，每条事件一行

3. 在 Field 卡片操作栏新增"录入事件"按钮：
   - 弹出表单（event_type / operator / note / inputs）
   - POST `/farm-agent/events`（B9 需补一个 POST endpoint，可选）

**预计工作量**：1 天

---

#### F4+F5 Dashboard 健康分 + 任务完成刷新

**文件**：[frontend-react/src/pages/Dashboard.tsx](file:///e:/GithubProgram/AgroAgentOS/frontend-react/src/pages/Dashboard.tsx)

**改动**：
1. 新增"农场健康分"卡片：
   - 查询 `listFarmProposals({ status: "pending" })` + `listFarmTasks({ status: ... })`
   - 计算 health_score = 100 - (high_risks * 20) - (medium_risks * 10) - (overdue_tasks * 5)
   - 圆形进度条 + 颜色（绿/黄/红）+ 子指标分解

2. 在 FarmTaskBoard 任务完成回调后，invalidate `["farm-agent-events", farmId]` 查询键：
   - 修改 [FarmAgent.tsx:42-47](file:///e:/GithubProgram/AgroAgentOS/frontend-react/src/pages/FarmAgent.tsx#L42-L47) `refreshWorkflow`：
     ```ts
     await Promise.all([
       queryClient.invalidateQueries({ queryKey: ["farm-agent-proposals", farmId] }),
       queryClient.invalidateQueries({ queryKey: ["farm-agent-tasks", farmId] }),
       queryClient.invalidateQueries({ queryKey: ["farm-agent-events", farmId] }),
       queryClient.invalidateQueries({ queryKey: ["farm-agent-sensors", farmId] }),
     ]);
     ```

**预计工作量**：0.5 天

---

### Week 4 — 文档与端到端验证

#### DOC1 演示剧本

**文件**：`docs/competition-demo-script.md`（新建）

**内容**：详见本计划第五章"10 步演示剧本"

#### DOC2 架构说明文档

**文件**：`docs/competition-architecture.md`（新建）

**内容大纲**：
1. 项目背景与目标
2. 整体架构图（FastAPI + LangGraph + React）
3. 农场管理 × AI 驾驶舱联动设计（三表事实表 + 事件流）
4. 比赛演示场景机制（fixture + inject + 幂等）
5. 风险规则确定性保证（非 LLM 判定）
6. 任务状态机与事件溯源
7. 验证与测试覆盖

**预计工作量**：1 天

#### 端到端验证（4 场景走通）

**验证流程**：
1. 启动后端：`uvicorn app.main:app --reload --port 9800`
2. 启动前端：`cd frontend-react && npm run dev`
3. 创建农场"南京试验农场" + 3 个地块（A1/A2/A3，与 fixture 字段名一致）
4. 在 FarmAgent 页面依次注入 4 个场景，每次启动巡检，验证：
   - rainstorm → `weather.rainstorm_drainage` high 风险 + 排水清沟提案
   - pest_outbreak → `pest.outbreak` high 风险 + 喷药提案
   - nutrient_deficiency → `nutrient.deficiency` medium 风险 + 追肥提案
   - drought → `drought.stress` high 风险 + 灌溉提案
5. 每个场景：批准提案 → 任务生成 → 开始 → 提交 → AI 复核 → 人工完成 → 验证 FarmEvent 写入
6. 切换到 Farms 页面，验证茬次卡片与事件时间线更新
7. 切换到 Dashboard，验证健康分随风险数变化

**预计工作量**：1.5 天

---

## 五、10 步演示剧本

| 步骤 | 时长 | 操作 | 预期效果 | 讲解要点 |
|------|------|------|----------|----------|
| 1 | 1 min | 自我介绍 + 项目背景 | 投影封面 | "AgroAgentOS 是 FastAPI + LangGraph 多 agent 农业平台" |
| 2 | 1 min | 展示 Farms 页面 | 3 个地块卡片 + 茬次信息 + 时间线 | "农场管理是事实底座，茬次表把作物生命周期结构化" |
| 3 | 1 min | 切到 Dashboard | 健康分 100 分 | "Dashboard 是经营视图，所有指标都来自下面的真实数据" |
| 4 | 1 min | 切到 FarmAgent 页面 | 三栏布局：风险态势 / 时间线 / 提案 | "AI 驾驶舱是闭环核心：感知→认知→决策" |
| 5 | 1.5 min | 选 rainstorm 场景，点击"注入感知数据" | 看到 `scenario_injected` SSE + SensorPanel 显示 6 条 | "无硬件也能演示：fixture 模拟田间传感器读数" |
| 6 | 2 min | 点击"开始 AI 综合巡检" | SSE 流式输出 plan/tool_call/proposal_created | "LangGraph 把判断变成可审计步骤，每条风险都带证据" |
| 7 | 1.5 min | 风险卡片显示 weather.rainstorm_drainage high | 看到证据列表（土壤含水量 95%、降雨 158mm） | "确定性规则保证可复现，不靠 LLM 拍脑袋" |
| 8 | 1.5 min | 批准排水清沟提案 | 任务出现在 FarmTaskBoard | "人工最终拍板，AI 只起草不执行" |
| 9 | 2 min | 任务开始 → 提交 → AI 复核 → 人工完成 | FarmEventTimeline 出现"排水清沟"事件 | "任务完成自动写事件，形成不可变记忆" |
| 10 | 1.5 min | 切到 pest_outbreak 场景，再次注入+巡检 | AI 报告中引用"7 天前刚排过水" | "事件流让 AI 有记忆，避免重复决策" |

**总时长**：约 14 分钟，可压缩到 10 分钟或扩展到 20 分钟

---

## 六、4 周任务分解甘特图

```
Week 1 (已完成)                              [████████████████████]
  ✅ B1+B2+B3 数据模型迁移
  ✅ B5 demo_scenario_service
  ✅ D1 4 个 fixture
  ⏳ T2+T4 测试（挪到 Week 2 末）

Week 2 — 业务逻辑层                          [████████████████████]
  Day 1-2: B6 风险规则扩展
  Day 2:   B7 snapshot 扩展
  Day 3:   B8 任务完成写事件
  Day 3:   B10+B11 枚举扩展+注入
  Day 4-5: T1+T2+T3+T4 测试

Week 3 — API + 前端                          [████████████████████]
  Day 1:   B9 API 路由
  Day 2-3: F1+F3 FarmAgent 场景选择器+感知面板
  Day 4:   F2 Farms 茬次卡片+时间线
  Day 5:   F4+F5 Dashboard 健康分+刷新

Week 4 — 文档与端到端                        [████████████████████]
  Day 1-2: DOC1+DOC2 文档
  Day 3-4: 端到端 4 场景走通 + bug 修复
  Day 5:   演示彩排 + 备份
```

---

## 七、Assumptions & Decisions

### 假设
1. **比赛时间窗口 3-4 周**，每周 5 工作日，每天 4-6 小时投入
2. **无硬件设备**，所有感知数据来自 fixture 文件
3. **演示形态**："先演示后自由"，即评委先看引导式演示，再自由提问
4. **同一农场贯穿 4 个场景**：A1 水稻 / A2 玉米 / A3 大豆，茬次表确保作物生命周期连续
5. **DashScope API 可用**：LLM 调用不降级
6. **SQLite 默认数据库**：USE_SQLITE=true，无需 MySQL/Milvus

### 关键决策
1. **风险判定用确定性阈值，不用 LLM**：保证比赛现场可复现，避免 LLM 输出波动
2. **LLM 仅用于生成提案标题/说明/指令文本**：仍走 ProposalDraft schema 校验
3. **场景注入是幂等的**：重复注入不会创建重复 sensor_readings，方便彩排
4. **事件流是 append-only**：FarmEvent 只插入不更新，`uq_event_task_type` 约束保证任务事件去重
5. **Field 与 CropSeason 双向同步**：Field.current_season_id 指针 + 冗余字段同步，兼容老代码
6. **frontend demoMode 改为 selectedScenario**：从布尔开关升级为 4 选 1 下拉，可独立注入也可巡检时注入
7. **健康分公式简单可解释**：`100 - high_risks*20 - medium_risks*10 - overdue_tasks*5`，便于现场讲解
8. **不实现 IoT 实时接入**：所有"感知"通过 fixture 注入，符合无硬件约束

### 已识别风险
- **风险 1**：FarmAgent.tsx 改动较大，可能破坏现有 SSE 流式逻辑 → 缓解：保留 inspect 函数主体，只改 demo_scenario 参数
- **风险 2**：4 个场景 fixture 的字段名必须与 DB 中 Field.name 完全匹配 → 缓解：演示前用种子脚本创建 A1/A2/A3
- **风险 3**：健康分公式过于简化可能被评委质疑 → 缓解：DOC2 文档中说明"V1 简化版，V2 可加入产量预测"
- **风险 4**：比赛现场网络不稳定导致 DashScope 调用失败 → 缓解：准备好本地 Ollama fallback 演示

---

## 八、Verification（验证步骤）

### 单元测试验证
```bash
# Week 2 末执行
pytest tests/services/test_farm_risk_service_pest_nutrient_drought.py -v
pytest tests/services/test_farm_task_event_flow.py -v
pytest tests/services/test_demo_scenario_service.py -v
pytest tests/services/test_crop_season_lifecycle.py -v
```

### API 集成验证
```bash
# Week 3 末执行
# 1. 启动后端
uvicorn app.main:app --reload --port 9800

# 2. 验证 5 个新 endpoint
curl -X GET http://localhost:9800/api/v1/farm-agent/scenarios -H "Authorization: Bearer $TOKEN"
curl -X POST http://localhost:9800/api/v1/farm-agent/scenarios/rainstorm/inject \
  -H "Authorization: Bearer $TOKEN" -d '{"farm_id": 1}'
curl -X GET "http://localhost:9800/api/v1/farm-agent/sensors?farm_id=1&days=7" -H "Authorization: Bearer $TOKEN"
curl -X GET "http://localhost:9800/api/v1/farm-agent/events?farm_id=1&days=14" -H "Authorization: Bearer $TOKEN"
curl -X GET "http://localhost:9800/api/v1/farm-agent/seasons?farm_id=1" -H "Authorization: Bearer $TOKEN"
```

### 端到端验证（Week 4）
1. 启动后端 + 前端
2. 创建农场"南京试验农场" + 3 个地块（A1/A2/A3）
3. 依次注入 4 个场景，每个场景执行完整闭环：注入 → 巡检 → 提案 → 任务 → 完成 → 事件
4. 验证：
   - 每个场景生成对应的期望风险（high/medium/high/high）
   - 任务完成时 FarmEvent 表新增 1 条
   - Farms 页面茬次卡片更新
   - Dashboard 健康分变化
   - 切换到下一个场景时，AI 报告能引用上个场景的事件

### 演示彩排验证（Week 4 末）
- 完整跑一遍 10 步演示剧本，计时 ≤ 15 分钟
- 模拟评委提问场景：临时注入一个不同场景看 AI 反应
- 网络故障演练：断网后用 Ollama fallback 仍能完成巡检

---

## 九、文件清单（按创建/修改分类）

### 新建文件（11 个）

| 路径 | 用途 | 周次 |
|------|------|------|
| `tests/services/test_farm_risk_service_pest_nutrient_drought.py` | T1 风险规则测试 | W2 |
| `tests/services/test_farm_task_event_flow.py` | T3 事件流测试 | W2 |
| `tests/services/test_demo_scenario_service.py` | T2 场景加载测试 | W2 |
| `tests/services/test_crop_season_lifecycle.py` | T4 茬次生命周期测试 | W2 |
| `frontend-react/src/components/farm-agent/SensorPanel.tsx` | F3 感知面板 | W3 |
| `frontend-react/src/components/farm-agent/FarmEventTimeline.tsx` | F3 事件时间线 | W3 |
| `docs/competition-demo-script.md` | DOC1 演示剧本 | W4 |
| `docs/competition-architecture.md` | DOC2 架构说明 | W4 |
| `scripts/seed_demo_farm.py` | 演示种子脚本（创建 A1/A2/A3） | W4 |
| `scripts/run_demo_e2e.py` | 端到端验证脚本 | W4 |

### 修改文件（10 个）

| 路径 | 改动要点 | 周次 |
|------|----------|------|
| [app/services/farm_risk_service.py](file:///e:/GithubProgram/AgroAgentOS/app/services/farm_risk_service.py) | +3 风险规则函数 + inspect_farm 改造 | W2 |
| [app/services/farm_snapshot_service.py](file:///e:/GithubProgram/AgroAgentOS/app/services/farm_snapshot_service.py) | +2 字段 +2 Pydantic 模型 + get_snapshot 查询 | W2 |
| [app/services/farm_task_service.py](file:///e:/GithubProgram/AgroAgentOS/app/services/farm_task_service.py) | complete() 写 FarmEvent + 3 辅助函数 | W2 |
| [app/schemas/farm_agent.py](file:///e:/GithubProgram/AgroAgentOS/app/schemas/farm_agent.py) | demo_scenario 扩展 4 值 + 3 Response 模型 | W2+W3 |
| [app/services/farm_agent_service.py](file:///e:/GithubProgram/AgroAgentOS/app/services/farm_agent_service.py) | stream_inspection 内注入场景 | W2 |
| [app/api/v1/farm_agent.py](file:///e:/GithubProgram/AgroAgentOS/app/api/v1/farm_agent.py) | +5 endpoint | W3 |
| [frontend-react/src/api/farmAgent.ts](file:///e:/GithubProgram/AgroAgentOS/frontend-react/src/api/farmAgent.ts) | +5 API 函数 + 类型定义 | W3 |
| [frontend-react/src/pages/FarmAgent.tsx](file:///e:/GithubProgram/AgroAgentOS/frontend-react/src/pages/FarmAgent.tsx) | demoMode→selectedScenario + SensorPanel + EventTimeline | W3 |
| [frontend-react/src/pages/Farms.tsx](file:///e:/GithubProgram/AgroAgentOS/frontend-react/src/pages/Farms.tsx) | 茬次卡片 + 事件时间线 | W3 |
| [frontend-react/src/pages/Dashboard.tsx](file:///e:/GithubProgram/AgroAgentOS/frontend-react/src/pages/Dashboard.tsx) | 健康分卡片 + 任务完成刷新 | W3 |

---

## 十、执行优先级与依赖关系

```
B6 风险规则 ──────┐
                  ├──→ B7 snapshot ──→ B9 API ──→ F1+F3 FarmAgent ──→ F4 Dashboard
B8 任务写事件 ────┘                              │
                                                ├──→ F2 Farms
B10+B11 枚举+注入 ──→ T1+T2+T3+T4 测试 ──────────┘
                                                ↓
                                          DOC1+DOC2 文档
                                                ↓
                                          端到端验证
```

**关键路径**：B6 → B7 → B9 → F1+F3 → 端到端验证
**并行机会**：B8 与 B6 可并行；T1-T4 测试在对应业务代码完成后即可开始；F2 Farms 与 F1+F3 FarmAgent 可并行

---

## 十一、退出标准

Week 2 末：
- ✅ 4 个风险规则函数单测全绿
- ✅ 任务完成写 FarmEvent 单测全绿
- ✅ 场景注入幂等性单测全绿

Week 3 末：
- ✅ 5 个新 API endpoint 通过 curl 验证
- ✅ FarmAgent 页面可下拉选 4 个场景并注入
- ✅ Farms 页面显示茬次卡片和事件时间线
- ✅ Dashboard 显示健康分

Week 4 末：
- ✅ 10 步演示剧本完整跑通，时长 ≤ 15 分钟
- ✅ 4 个场景端到端走通，每个场景生成对应期望风险
- ✅ 文档 2 篇完成
- ✅ 演示彩排 1 次成功
