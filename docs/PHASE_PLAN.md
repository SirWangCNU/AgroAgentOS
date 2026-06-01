# AgroAgentOS 阶段计划：从问答 Agent 到农业数字化管理平台

> 仿照 smartcrop.cn 的农场管理、地块管理、农事管理、生长预测等模块，
> 将现有系统从"智能问答 Agent"升级为"农业数字化管理平台"。

---

## 整体架构演进

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        AgroAgentOS 智农协同平台 v2.0                      │
├─────────────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌────────────┐  │
│  │  农场管理     │  │  地块管理     │  │  农事管理     │  │  生长预测   │  │
│  │  Farm Mgmt   │  │  Field Mgmt  │  │  Activity    │  │  Growth    │  │
│  │              │  │              │  │  Mgmt        │  │  Prediction│  │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └─────┬──────┘  │
│         │                 │                 │                │         │
│         ▼                 ▼                 ▼                ▼         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                    Multi-Agent 协同引擎 (已有)                    │   │
│  │         SkillRouter → Planner → Executor → Replanner            │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│         │                 │                 │                │         │
│         ▼                 ▼                 ▼                ▼         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌────────────┐  │
│  │  知识库 RAG   │  │  天气 API    │  │  数据分析     │  │  智能预警   │  │
│  │  (已有)       │  │  (已有)       │  │  (新增)       │  │  (新增)    │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  └────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 阶段四：农场与地块管理（基础数据层）

**目标**：建立农业生产的空间数据基础，让用户能管理自己的农场和地块。

### 4.1 数据库模型设计

```
Farm (农场)
├── id: int (PK)
├── user_id: int (FK → User)
├── name: str (农场名称)
├── location: str (地址)
├── latitude: float (纬度)
├── longitude: float (经度)
├── area_mu: float (总面积/亩)
├── description: str (描述)
├── created_at: datetime
└── updated_at: datetime

Field (地块)
├── id: int (PK)
├── farm_id: int (FK → Farm)
├── name: str (地块名称, 如"东边大田")
├── area_mu: float (面积/亩)
├── soil_type: str (土壤类型: 沙土/黏土/壤土)
├── current_crop: str (当前作物)
├── planting_date: date (播种日期)
├── expected_harvest: date (预计收获日期)
├── growth_stage: str (生长阶段)
├── status: str (状态: 空闲/种植中/休耕)
├── latitude: float (纬度)
├── longitude: float (经度)
├── notes: str (备注)
├── created_at: datetime
└── updated_at: datetime
```

### 4.2 API 端点

```
POST   /api/v1/farms              # 创建农场
GET    /api/v1/farms              # 获取用户所有农场
GET    /api/v1/farms/{id}         # 获取农场详情
PUT    /api/v1/farms/{id}         # 更新农场
DELETE /api/v1/farms/{id}         # 删除农场

POST   /api/v1/farms/{id}/fields  # 在农场下创建地块
GET    /api/v1/farms/{id}/fields  # 获取农场所有地块
GET    /api/v1/fields/{id}        # 获取地块详情
PUT    /api/v1/fields/{id}        # 更新地块
DELETE /api/v1/fields/{id}        # 删除地块
GET    /api/v1/fields/{id}/weather # 获取地块所在位置天气
```

### 4.3 前端页面

```
农场管理页面:
├── 农场卡片列表 (名称、位置、面积、地块数)
├── 新增/编辑农场弹窗
├── 农场详情页
│   ├── 基本信息卡片
│   ├── 地块列表 (卡片/表格切换)
│   ├── 地块地图标注 (可选, 用高德/腾讯地图)
│   └── 快捷操作 (添加地块、查看天气、开始诊断)
└── 删除确认弹窗

地块管理页面:
├── 地块卡片 (名称、面积、作物、生长阶段、状态)
├── 新增/编辑地块弹窗
├── 地块详情页
│   ├── 基本信息
│   ├── 当前作物信息
│   ├── 生长时间线
│   └── 关联的农事记录
└── 作物选择器 (常见作物下拉)
```

### 4.4 Agent 集成

```python
# 新增 Skill: field_diagnosis
# 当用户选择某地块进行诊断时，自动注入地块上下文：
# "用户正在查看地块: 东边大田 (水稻, 已种植45天, 拔节期)"
# Agent 可以基于地块信息给出更精准的建议
```

### 4.5 文件清单

| 文件 | 说明 |
|------|------|
| `app/models/farm.py` | Farm ORM 模型 |
| `app/models/field.py` | Field ORM 模型 |
| `app/api/v1/farms.py` | 农场 CRUD API |
| `app/api/v1/fields.py` | 地块 CRUD API |
| `app/schemas/farm.py` | Farm Pydantic schema |
| `app/schemas/field.py` | Field Pydantic schema |
| `alembic/versions/003_add_farm_field.py` | 数据库迁移 |
| `frontend/pages/farms.html` | 农场管理页面 |
| `frontend/pages/fields.html` | 地块管理页面 |
| `frontend/js/farm.js` | 农场前端逻辑 |
| `frontend/js/field.js` | 地块前端逻辑 |

---

## 阶段五：农事管理（活动记录层）

**目标**：记录和管理农业生产活动，形成完整的农事档案。

### 5.1 数据库模型设计

```
Activity (农事活动)
├── id: int (PK)
├── field_id: int (FK → Field)
├── user_id: int (FK → User)
├── activity_type: str (活动类型)
│   ├── planting    # 播种
│   ├── fertilizing # 施肥
│   ├── watering    # 浇水/灌溉
│   ├── spraying    # 打药/喷药
│   ├── weeding     # 除草
│   ├── pruning     # 修剪
│   ├── harvesting  # 收获
│   └── other       # 其他
├── title: str (活动标题)
├── description: str (详细描述)
├── activity_date: datetime (活动时间)
├── materials: JSON (使用的物资, 如农药名称、用量)
│   示例: [{"name": "吡虫啉", "amount": "50g/亩", "purpose": "防治蚜虫"}]
├── weather_snapshot: JSON (活动时天气快照)
│   示例: {"temp": 28, "humidity": 65, "wind": "3级", "weather": "晴"}
├── cost: float (成本/元)
├── photos: JSON (照片路径列表)
├── source: str (来源: manual/agent/auto)
│   ├── manual  # 用户手动记录
│   ├── agent   # Agent 诊断后建议记录
│   └── auto    # 系统自动记录 (如定时提醒)
├── agent_task_id: str (关联的 Agent 任务ID, source=agent时)
├── created_at: datetime
└── updated_at: datetime

ActivityTemplate (农事模板 - 可选)
├── id: int (PK)
├── crop: str (适用作物)
├── growth_stage: str (生长阶段)
├── activity_type: str (活动类型)
├── title: str (模板标题)
├── description: str (模板描述)
├── recommended_materials: JSON (推荐物资)
└── timing_advice: str (时机建议)
```

### 5.2 API 端点

```
POST   /api/v1/fields/{id}/activities     # 在地块下记录农事
GET    /api/v1/fields/{id}/activities     # 获取地块农事记录
GET    /api/v1/activities/{id}            # 获取农事详情
PUT    /api/v1/activities/{id}            # 更新农事记录
DELETE /api/v1/activities/{id}            # 删除农事记录
GET    /api/v1/activities/calendar        # 获取农事日历 (按月)
GET    /api/v1/activities/timeline        # 获取农事时间线
GET    /api/v1/activities/stats           # 获取农事统计
```

### 5.3 前端页面

```
农事管理页面:
├── 农事日历视图
│   ├── 月历展示 (每天显示活动图标)
│   ├── 点击日期查看当天活动
│   └── 快速添加活动
├── 农事时间线视图
│   ├── 按时间倒序展示所有活动
│   ├── 活动卡片 (类型图标、标题、日期、地块)
│   └── 筛选 (按地块、按类型、按时间)
├── 新增/编辑活动弹窗
│   ├── 活动类型选择 (图标按钮组)
│   ├── 关联地块选择
│   ├── 日期时间选择
│   ├── 物资添加 (动态表单)
│   ├── 照片上传
│   └── 成本输入
└── 农事统计面板
    ├── 各类型活动次数饼图
    ├── 月度活动趋势折线图
    └── 成本统计柱状图
```

### 5.4 Agent 集成

```python
# 1. Agent 诊断后自动建议记录农事
#    诊断结果: "建议明天上午喷施吡虫啉防治蚜虫"
#    → 自动生成一条 activity 记录 (source=agent, status=pending)
#    → 用户确认后生效

# 2. 农事记录作为 Agent 上下文
#    用户问: "我这块地最近该做什么？"
#    → Agent 读取该地块的最近 10 条农事记录
#    → 结合作物、生长阶段、天气，给出建议

# 3. 新增 Skill: activity_advisor (农事顾问)
#    触发词: "该做什么"、"下一步"、"农事安排"
#    工具: get_field_activities, get_weather, search_knowledge_base
```

### 5.5 文件清单

| 文件 | 说明 |
|------|------|
| `app/models/activity.py` | Activity ORM 模型 |
| `app/api/v1/activities.py` | 农事 CRUD API |
| `app/schemas/activity.py` | Activity Pydantic schema |
| `alembic/versions/004_add_activity.py` | 数据库迁移 |
| `frontend/pages/activities.html` | 农事管理页面 |
| `frontend/js/activity.js` | 农事前端逻辑 |
| `frontend/js/calendar.js` | 日历组件 |
| `app/skills/definitions/activity_advisor/SKILL.md` | 农事顾问 Skill |

---

## 阶段六：生长预测与数据分析（智能分析层）

**目标**：基于历史数据和环境信息，预测作物生长趋势，提供数据驱动的决策支持。

### 6.1 数据库模型设计

```
GrowthRecord (生长记录)
├── id: int (PK)
├── field_id: int (FK → Field)
├── record_date: date (记录日期)
├── growth_stage: str (生长阶段)
├── height_cm: float (株高/cm)
├── leaf_count: int (叶片数)
├── health_score: int (健康评分 1-10)
├── notes: str (观察记录)
├── photos: JSON (照片列表)
├── weather_snapshot: JSON (记录时天气)
└── created_at: datetime

CropCalendar (作物日历 - 预置数据)
├── id: int (PK)
├── crop: str (作物名称)
├── variety: str (品种, 可选)
├── growth_stages: JSON (生长阶段定义)
│   示例: [
│     {"name": "播种期", "days": [0, 7], "description": "..."},
│     {"name": "出苗期", "days": [7, 21], "description": "..."},
│     {"name": "分蘖期", "days": [21, 50], "description": "..."},
│     {"name": "拔节期", "days": [50, 75], "description": "..."},
│     {"name": "抽穗期", "days": [75, 95], "description": "..."},
│     {"name": "灌浆期", "days": [95, 120], "description": "..."},
│     {"name": "成熟期", "days": [120, 150], "description": "..."}
│   ]
├── optimal_temp: JSON (适宜温度范围)
├── water_needs: JSON (需水量)
├── common_pests: JSON (常见病虫害)
└── key_activities: JSON (关键农事活动)

Prediction (预测结果)
├── id: int (PK)
├── field_id: int (FK → Field)
├── prediction_type: str (预测类型)
│   ├── growth_stage   # 生长阶段预测
│   ├── harvest_date   # 收获时间预测
│   ├── yield          # 产量预测
│   └── risk           # 风险预测
├── prediction_date: date (预测日期)
├── predicted_value: JSON (预测值)
├── confidence: float (置信度 0-1)
├── factors: JSON (影响因素)
├── model_version: str (模型版本)
└── created_at: datetime
```

### 6.2 生长预测算法

```python
# 第一版: 基于规则的预测 (无需 ML)
class GrowthPredictor:
    def predict_growth_stage(self, field: Field) -> Prediction:
        """基于播种日期和作物日历预测当前生长阶段"""
        days_since_planting = (today - field.planting_date).days
        calendar = get_crop_calendar(field.current_crop)
        stage = calendar.get_stage_by_days(days_since_planting)
        return Prediction(
            predicted_value={"stage": stage.name, "progress": stage.progress},
            confidence=0.9,  # 规则预测置信度高
            factors=["播种日期", "作物日历"]
        )

    def predict_harvest_date(self, field: Field) -> Prediction:
        """预测收获时间"""
        calendar = get_crop_calendar(field.current_crop)
        total_days = calendar.total_growth_days
        expected_harvest = field.planting_date + timedelta(days=total_days)
        # 根据天气调整
        weather_factor = self._calc_weather_adjustment(field)
        adjusted_harvest = expected_harvest + timedelta(days=weather_factor)
        return Prediction(...)

    def predict_risk(self, field: Field) -> Prediction:
        """预测风险 (病虫害、气象灾害)"""
        # 结合: 生长阶段 + 天气预报 + 知识库
        risks = []
        weather = get_weather_forecast(field.latitude, field.longitude, days=7)
        stage = self.predict_growth_stage(field)
        # 查询知识库: "水稻 拔节期 常见病害"
        knowledge = search_knowledge_base(f"{field.current_crop} {stage} 病害")
        ...
```

### 6.3 API 端点

```
GET    /api/v1/fields/{id}/growth         # 获取生长预测
GET    /api/v1/fields/{id}/growth/history  # 获取生长记录历史
POST   /api/v1/fields/{id}/growth/record   # 记录生长数据
GET    /api/v1/fields/{id}/yield           # 获取产量预测
GET    /api/v1/fields/{id}/risk            # 获取风险预测
GET    /api/v1/crop-calendar/{crop}        # 获取作物日历
GET    /api/v1/dashboard/overview          # 数据概览
```

### 6.4 前端页面

```
生长预测页面:
├── 生长进度卡片
│   ├── 当前阶段 (图标 + 文字)
│   ├── 进度条 (播种 → 成熟)
│   ├── 已生长天数 / 预计总天数
│   └── 下一阶段预计时间
├── 生长曲线图
│   ├── 株高变化折线图
│   ├── 健康评分趋势
│   └── 关键节点标注
├── 风险预警卡片
│   ├── 病虫害风险等级 (红/黄/绿)
│   ├── 气象灾害风险
│   └── 防治建议
├── 产量预测卡片
│   ├── 预计产量
│   ├── 置信度
│   └── 影响因素分析
└── 数据录入弹窗
    ├── 生长数据 (株高、叶片数、健康评分)
    ├── 照片上传
    └── 观察记录

数据概览 Dashboard:
├── 农场总览卡片 (农场数、地块数、总面积)
├── 各地块状态分布 (饼图: 空闲/种植中/休耕)
├── 近期农事日历 (7天)
├── 待办事项 (需要关注的地块)
├── 天气概况 (所有农场位置)
└── 成本统计 (月度/季度)
```

### 6.5 文件清单

| 文件 | 说明 |
|------|------|
| `app/models/growth.py` | GrowthRecord, CropCalendar, Prediction 模型 |
| `app/api/v1/growth.py` | 生长预测 API |
| `app/api/v1/dashboard.py` | 数据概览 API |
| `app/services/growth_predictor.py` | 生长预测算法 |
| `app/data/crop_calendar.py` | 作物日历预置数据 |
| `alembic/versions/005_add_growth.py` | 数据库迁移 |
| `frontend/pages/growth.html` | 生长预测页面 |
| `frontend/pages/dashboard.html` | 数据概览页面 |
| `frontend/js/growth.js` | 生长预测前端逻辑 |
| `frontend/js/dashboard.js` | 仪表盘前端逻辑 |
| `frontend/js/charts.js` | 图表组件 (ECharts) |

---

## 阶段七：智能预警与自动化（自动化层）

**目标**：基于规则和 Agent 实现农业生产自动化提醒和预警。

### 7.1 数据库模型设计

```
AlertRule (预警规则)
├── id: int (PK)
├── user_id: int (FK → User)
├── field_id: int (FK → Field, 可选, 为空则全局)
├── rule_type: str (规则类型)
│   ├── weather       # 天气预警 (降温/暴雨/大风)
│   ├── growth_stage  # 生长阶段提醒 (进入新阶段)
│   ├── activity      # 农事提醒 (该施肥了/该打药了)
│   ├── pest_risk     # 病虫害风险
│   └── custom        # 自定义规则
├── name: str (规则名称)
├── conditions: JSON (触发条件)
│   示例 (天气): {"type": "temp_drop", "threshold": 5, "duration_hours": 24}
│   示例 (农事): {"crop": "水稻", "stage": "拔节期", "activity": "施肥", "days_after": 3}
├── notify_channels: JSON (通知渠道)
│   示例: ["web_push", "sms", "wechat"]
├── is_active: bool (是否启用)
├── last_triggered: datetime (上次触发时间)
├── created_at: datetime
└── updated_at: datetime

AlertRecord (预警记录)
├── id: int (PK)
├── rule_id: int (FK → AlertRule)
├── field_id: int (FK → Field)
├── triggered_at: datetime (触发时间)
├── title: str (预警标题)
├── message: str (预警内容)
├── severity: str (严重程度: info/warning/danger)
├── status: str (状态: pending/acknowledged/resolved)
├── agent_response: str (Agent 自动生成的建议)
├── acknowledged_at: datetime (确认时间)
└── created_at: datetime
```

### 7.2 预警引擎

```python
class AlertEngine:
    """预警引擎: 定时检查规则，触发预警"""

    async def check_weather_alerts(self):
        """检查天气预警"""
        rules = await get_active_rules(rule_type="weather")
        for rule in rules:
            weather = await get_weather_forecast(rule.field)
            if self._match_weather_condition(weather, rule.conditions):
                await self._trigger_alert(rule, weather)

    async def check_growth_stage_alerts(self):
        """检查生长阶段变化"""
        fields = await get_all_active_fields()
        for field in fields:
            prediction = await growth_predictor.predict_growth_stage(field)
            if prediction.stage_changed:
                await self._trigger_stage_alert(field, prediction)

    async def check_activity_reminders(self):
        """检查农事提醒"""
        fields = await get_all_active_fields()
        for field in fields:
            # 基于作物日历和天气，判断是否该做某项农事
            suggestions = await self._suggest_activities(field)
            if suggestions:
                await self._trigger_activity_reminder(field, suggestions)
```

### 7.3 Agent 集成

```python
# 预警触发时，自动调用 Agent 生成建议
async def _trigger_alert(self, rule, context):
    # 1. 创建预警记录
    alert = AlertRecord(rule_id=rule.id, ...)

    # 2. 调用 Agent 生成建议
    prompt = f"""
    农业预警: {alert.title}
    地块信息: {rule.field.name} ({rule.field.current_crop}, {rule.field.growth_stage})
    预警详情: {alert.message}
    请给出专业的应对建议。
    """
    agent_response = await run_agent(prompt, skill="agriculture_qa")
    alert.agent_response = agent_response

    # 3. 发送通知
    await send_notification(alert, rule.notify_channels)
```

### 7.4 前端页面

```
预警中心页面:
├── 预警列表
│   ├── 预警卡片 (类型图标、标题、时间、严重程度)
│   ├── 筛选 (按类型、按状态、按地块)
│   └── 点击展开详情 (Agent 建议)
├── 预警规则管理
│   ├── 规则列表 (名称、类型、状态、上次触发)
│   ├── 新建规则向导
│   └── 规则开关
├── 通知设置
│   ├── 通知渠道配置
│   └── 免打扰时段
└── 预警统计
    ├── 各类型预警次数
    └── 预警响应率
```

### 7.5 文件清单

| 文件 | 说明 |
|------|------|
| `app/models/alert.py` | AlertRule, AlertRecord 模型 |
| `app/api/v1/alerts.py` | 预警 API |
| `app/services/alert_engine.py` | 预警引擎 |
| `app/tasks/alert_checker.py` | 定时检查任务 |
| `alembic/versions/006_add_alerts.py` | 数据库迁移 |
| `frontend/pages/alerts.html` | 预警中心页面 |
| `frontend/js/alerts.js` | 预警前端逻辑 |

---

## 实施优先级与时间估算

| 阶段 | 模块 | 优先级 | 预估工作量 | 依赖 |
|------|------|--------|-----------|------|
| **阶段四** | 农场与地块管理 | P0 | 3-4 天 | 无 |
| **阶段五** | 农事管理 | P0 | 3-4 天 | 阶段四 |
| **阶段六** | 生长预测与数据分析 | P1 | 4-5 天 | 阶段四、五 |
| **阶段七** | 智能预警与自动化 | P1 | 3-4 天 | 阶段四、五、六 |

### 建议实施顺序

```
阶段四 (农场/地块) ──▶ 阶段五 (农事管理) ──▶ 阶段六 (生长预测) ──▶ 阶段七 (智能预警)
     │                      │                      │                      │
     │                      │                      │                      │
     ▼                      ▼                      ▼                      ▼
  基础数据层              活动记录层             智能分析层             自动化层
  (先让用户能管理         (记录农事活动,        (基于数据做预测,       (自动化提醒,
   农场和地块)            形成完整档案)         提供决策支持)          减少人工干预)
```

---

## 技术要点

### 前端技术选型

```
当前: 原生 HTML + JS + TailwindCSS
新增:
├── ECharts (图表库) - 生长曲线、统计图表
├── FullCalendar (日历库) - 农事日历
├── 高德/腾讯地图 JS API - 地块地图标注 (可选)
└── PWA 支持 - 离线访问、推送通知 (可选)
```

### 数据库

```
当前: SQLite
建议: 保持 SQLite (单用户场景足够)
如需多用户/多设备同步: 迁移到 PostgreSQL
```

### 与现有 Agent 系统集成

```
1. 地块上下文注入: 选择地块时，自动将地块信息注入 Agent 上下文
2. 农事记录联动: Agent 诊断后可一键生成农事记录
3. 预警触发 Agent: 预警触发时自动调用 Agent 生成建议
4. 生长数据作为 RAG: 生长记录可作为 RAG 检索的上下文
```

---

## 里程碑检查点

### 阶段四完成标准
- [ ] 用户可以创建/编辑/删除农场
- [ ] 用户可以在农场下创建/编辑/删除地块
- [ ] 地块卡片显示作物、生长阶段、状态
- [ ] 地块详情页显示基本信息和关联数据
- [ ] API 文档完整，前端页面可正常使用

### 阶段五完成标准
- [ ] 用户可以记录 8 种类型的农事活动
- [ ] 农事日历视图正常显示
- [ ] 农事时间线可筛选和排序
- [ ] Agent 诊断后可一键生成农事记录
- [ ] 农事记录可作为 Agent 上下文

### 阶段六完成标准
- [ ] 作物日历数据完整（水稻、小麦、玉米、蔬菜）
- [ ] 生长阶段预测准确（基于播种日期）
- [ ] 收获时间预测可用
- [ ] 风险预测基于天气+知识库
- [ ] Dashboard 数据概览页面可用
- [ ] 图表展示正常（ECharts）

### 阶段七完成标准
- [ ] 天气预警规则可配置
- [ ] 生长阶段提醒自动触发
- [ ] 农事提醒基于作物日历
- [ ] 预警触发时 Agent 自动生成建议
- [ ] 预警中心页面可用
