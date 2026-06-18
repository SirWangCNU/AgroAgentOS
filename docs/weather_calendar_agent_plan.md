# 天气与种植历 Agent（weather_advice）详细实施方案

> 范围：在现有 `weather_advice` Skill 基础上，新增"全年种植历生成"、"节气农事提醒"、
> "极端天气预警"三项能力，补齐原产品设计中第 4.4 节规划的全部功能。
> 架构不变：仍是 inline Skill，运行在同一张 Plan-Execute-Replan 图中。

---

## 1. 现状与目标能力对照

| 能力 | 现状 | 说明 |
|---|---|---|
| 天气查询 + 农事解读 | ✅ 已有 | `get_weather_forecast` + `get_agri_weather_advice` |
| 极端天气预警 | ❌ 待补 | 复用现有预报数据做后处理，不需要新数据源 |
| 节气农事提醒 | ❌ 待补 | 需新增节气计算 + 提醒文案库 |
| 全年种植历 | ❌ 待补 | 需新增作物种植历模板 + 纬度分区逻辑 |

---

## 2. SKILL.md 完整设计

**文件**：`app/skills/definitions/weather_advice/SKILL.md`

```yaml
---
name: weather_advice
description: 天气查询、农事天气建议、极端天气预警、种植历与节气提醒
context: inline
allowed_tools:
  - get_weather_forecast
  - get_agri_weather_advice
  - generate_planting_calendar
  - solar_term_reminder
triggers:
  - 天气
  - 下雨
  - 气温
  - 种植历
  - 节气
  - 播种期
  - 霜冻
  - 暴雨
  - 预警
  - 全年安排
---

# 天气与种植历技能

## 操作指南 (Playbook)

1. **判断查询类型**：天气查询 / 种植历生成 / 节气提醒 / 极端天气预警，可能同时涉及多种

2. **天气查询**：
   - 调用 get_weather_forecast 获取未来 7 天预报
   - 检查返回结果中的 `alerts` 字段（极端天气预警），若非空，
     **必须在回复开头**先给出预警提示，再回答天气详情
   - 结合用户地块的 current_crop，调用 get_agri_weather_advice 给出"农业视角"解读
     （例如"本周三有大雨，建议提前检查排水"）

3. **种植历请求**（如"全年怎么安排"、"今年种水稻的计划"）：
   - 调用 generate_planting_calendar(crop, latitude, longitude)
   - 按时间顺序展示各阶段及对应农事要点
   - 若某阶段类型为"施肥"，可在结尾提示"需要更详细的施肥配比建议吗"，
     为后续协作 crop_advisory 留出引导

4. **节气类请求**（如"现在是什么节气"、"清明前后要注意什么"）：
   - 调用 solar_term_reminder(date)
   - 结合用户的 current_crop（如有）筛选相关提醒，避免输出与用户作物无关的内容

5. **主动预警原则**：只要 get_weather_forecast 的结果中存在 alerts，
   无论用户问的是什么，都应在回复中提及，不要等用户追问
```

---

## 3. 核心工具详细设计

### 3.1 `get_weather_forecast`（现有，需扩展返回结构）

在现有实现基础上，增加 `alerts` 字段，调用内部的 `analyze_weather_risks` 做后处理：

```python
@tool
def get_weather_forecast(latitude: float, longitude: float, days: int = 7) -> WeatherForecastResult:
    """获取未来N天天气预报，并自动分析极端天气风险"""
    raw = call_weather_api(latitude, longitude, days)   # 现有逻辑不变
    alerts = analyze_weather_risks(raw)                  # 新增后处理
    return WeatherForecastResult(daily=raw, alerts=alerts)
```

**为什么不单独做一个 alert 工具**：极端天气预警依赖的就是天气预报数据本身，
拆成两个工具会导致 LLM 需要多一次调用才能拿到完整信息，增加延迟。
直接在现有工具的返回结构里加一个字段，对 Executor 和 Playbook 改动最小。

---

### 3.2 `analyze_weather_risks`（新增，内部函数，非 LLM 工具）

**文件**：`app/tools/weather_risk.py`（新建）

```python
def analyze_weather_risks(forecast: list[DailyForecast], crop: str | None = None) -> list[WeatherAlert]:
    """根据预报数据计算极端天气预警"""
    alerts = []
    for day in forecast:
        if day.min_temp <= 2:
            alerts.append(WeatherAlert(
                alert_type="霜冻", date=day.date, severity="中" if day.min_temp > 0 else "高",
                advice="夜间注意覆盖或熏烟防霜，敏感作物提前转移至室内"
            ))
        if day.precipitation_mm >= 50:
            severity = "高" if day.precipitation_mm >= 100 else "中"
            alerts.append(WeatherAlert(
                alert_type="暴雨", date=day.date, severity=severity,
                advice="检查排水沟渠，低洼地块提前排水，大棚加固"
            ))
        if day.max_temp >= 35:
            alerts.append(WeatherAlert(
                alert_type="高温", date=day.date, severity="中",
                advice="增加灌溉频次，叶面喷水降温，避免午间作业"
            ))
    # 连续无降水检测（简化：检查整个forecast窗口）
    if all(d.precipitation_mm < 1 for d in forecast) and len(forecast) >= 7:
        alerts.append(WeatherAlert(
            alert_type="干旱", date=forecast[0].date, severity="中",
            advice="未来一周基本无雨，提前规划灌溉"
        ))
    return alerts
```

**预警阈值参考**（可根据实际反馈调整）：

| 类型 | 阈值 | 严重度划分 |
|---|---|---|
| 霜冻 | 最低温 ≤ 2℃ | ≤0℃ 高，0-2℃ 中 |
| 暴雨 | 日降水 ≥ 50mm | ≥100mm 高，50-100mm 中 |
| 高温 | 最高温 ≥ 35℃ | 统一为中 |
| 干旱 | 连续7天降水 < 1mm | 统一为中 |

---

### 3.3 `solar_term_reminder`（新增）

**文件**：`app/tools/calendar_tools.py`（新建，与种植历共用一个文件）

```python
import cnlunar
from datetime import datetime

@tool
def solar_term_reminder(date: str | None = None, crop: str | None = None) -> SolarTermInfo:
    """返回指定日期对应的节气及相关农事提醒，可按作物过滤"""
    target_date = datetime.strptime(date, "%Y-%m-%d") if date else datetime.now()
    lunar = cnlunar.Lunar(target_date, godType='8char')
    term = lunar.term  # cnlunar 直接提供当前节气名称

    reminders = SOLAR_TERM_REMINDERS.get(term, {})
    general = reminders.get("general", [])
    crop_specific = reminders.get("crops", {}).get(crop, []) if crop else []

    return SolarTermInfo(
        term=term,
        date_range=reminders.get("date_range", ""),
        general_reminders=general,
        crop_reminders=crop_specific,
    )
```

**依赖库**：`pip install cnlunar` —— 这是一个成熟的农历/节气计算库，**不需要自己实现
节气算法**（节气日期计算涉及太阳黄经，手写容易出错，直接用现成库更可靠）。

---

### 3.4 `generate_planting_calendar`（新增）

```python
@tool
def generate_planting_calendar(crop: str, latitude: float, longitude: float) -> PlantingCalendar:
    """根据作物种类和地理位置生成全年种植历"""
    template = CROP_CALENDAR_TEMPLATES.get(crop)
    if not template:
        raise ToolError(f"暂未收录「{crop}」的种植历模板")

    zone = determine_climate_zone(latitude)   # 见3.4.1
    zone_config = template["zones"].get(zone, template["zones"]["华中"])  # 缺省回退

    sowing_start = parse_date(zone_config["sowing_window"].split("~")[0])
    stages = []
    for stage in template["stage_offsets_days"]:
        stage_date = sowing_start + timedelta(days=stage["offset"])
        stages.append(CalendarStage(
            name=stage["name"],
            date=stage_date.strftime("%m-%d"),
            category=stage["category"],
            note=stage["note"],
        ))

    return PlantingCalendar(crop=crop, zone=zone, stages=stages)
```

#### 3.4.1 气候分区简化方案

不做连续纬度插值（容易产生"伪精确"），改用**分区模板**，对农业场景更实用：

| 分区 | 纬度范围 | 代表区域 |
|---|---|---|
| 华南 | < 25°N | 广东、广西、海南、福建南部 |
| 华中/华东 | 25°N - 35°N | 长江流域、华东大部 |
| 华北 | 35°N - 42°N | 京津冀、山东、河南北部 |
| 东北/西北高纬 | ≥ 42°N | 黑龙江、吉林、内蒙古北部 |

```python
def determine_climate_zone(latitude: float) -> str:
    if latitude < 25:
        return "华南"
    elif latitude < 35:
        return "华中"
    elif latitude < 42:
        return "华北"
    else:
        return "东北"
```

---

## 4. 数据结构（Pydantic Schema）

**文件**：`app/schemas/weather.py`（新建）

```python
from pydantic import BaseModel

class WeatherAlert(BaseModel):
    alert_type: str   # 霜冻/暴雨/高温/干旱
    date: str
    severity: str      # 高/中/低
    advice: str

class DailyForecast(BaseModel):
    date: str
    min_temp: float
    max_temp: float
    precipitation_mm: float
    condition: str

class WeatherForecastResult(BaseModel):
    daily: list[DailyForecast]
    alerts: list[WeatherAlert] = []

class SolarTermInfo(BaseModel):
    term: str
    date_range: str
    general_reminders: list[str]
    crop_reminders: list[str] = []

class CalendarStage(BaseModel):
    name: str
    date: str          # MM-DD
    category: str      # 播种/施肥/防虫/管理/收获
    note: str

class PlantingCalendar(BaseModel):
    crop: str
    zone: str
    stages: list[CalendarStage]
```

---

## 5. 数据文件设计

### 5.1 `data/solar_terms.json`

只展示部分示例，需逐步补全 24 节气：

```json
{
  "立春": {
    "date_range": "02-03~02-05",
    "general": ["阳气回升，注意防范倒春寒"],
    "crops": {
      "冬小麦": ["返青前追肥一次，促进春季生长"]
    }
  },
  "清明": {
    "date_range": "04-04~04-06",
    "general": ["气温回升明显，多地进入春播高峰期"],
    "crops": {
      "玉米": ["华北地区春玉米适宜播种期"],
      "水稻": ["华南地区可开始早稻插秧"]
    }
  },
  "谷雨": {
    "date_range": "04-19~04-21",
    "general": ["降水增多，注意田间排水"],
    "crops": {
      "玉米": ["华中、华北地区春玉米播种适宜期"]
    }
  },
  "芒种": {
    "date_range": "06-05~06-07",
    "general": ["进入夏收夏种关键期"],
    "crops": {
      "水稻": ["长江流域中稻插秧高峰期"]
    }
  },
  "白露": {
    "date_range": "09-07~09-09",
    "general": ["昼夜温差加大，注意秋季作物防寒"],
    "crops": {
      "水稻": ["华中地区中稻陆续进入收获期"]
    }
  },
  "霜降": {
    "date_range": "10-23~10-24",
    "general": ["北方地区开始出现初霜，喜温作物需收尾"],
    "crops": {
      "玉米": ["华北玉米进入收获期，避免霜后晚收影响品质"]
    }
  }
}
```

### 5.2 `data/crop_calendar_templates.json`

示例覆盖 3 种主要作物，后续按需扩充：

```json
{
  "水稻": {
    "type": "粮食作物",
    "zones": {
      "华南": {"sowing_window": "02-01~03-15", "seasons": 2},
      "华中": {"sowing_window": "03-15~04-15", "seasons": 1},
      "华北": {"sowing_window": "04-15~05-15", "seasons": 1}
    },
    "stage_offsets_days": [
      {"name": "播种育秧", "offset": 0, "category": "播种", "note": "选用抗病品种，浸种消毒"},
      {"name": "移栽返青", "offset": 25, "category": "管理", "note": "保持浅水层，促进返青"},
      {"name": "分蘖期追肥", "offset": 35, "category": "施肥", "note": "氮肥为主，配施钾肥"},
      {"name": "病虫害高发期", "offset": 50, "category": "防虫", "note": "重点防稻飞虱、稻瘟病、纹枯病"},
      {"name": "拔节孕穗期", "offset": 65, "category": "施肥", "note": "增施磷钾肥，控制氮肥用量"},
      {"name": "收获期", "offset": 110, "category": "收获", "note": "九成黄即可适时收割"}
    ]
  },
  "玉米": {
    "type": "粮食作物",
    "zones": {
      "华南": {"sowing_window": "02-15~03-15", "seasons": 2},
      "华中": {"sowing_window": "04-01~04-25", "seasons": 1},
      "华北": {"sowing_window": "04-20~05-10", "seasons": 1},
      "东北": {"sowing_window": "04-25~05-15", "seasons": 1}
    },
    "stage_offsets_days": [
      {"name": "播种期", "offset": 0, "category": "播种", "note": "土壤温度稳定在10℃以上"},
      {"name": "苗期管理", "offset": 15, "category": "管理", "note": "及时间苗补苗"},
      {"name": "拔节期追肥", "offset": 35, "category": "施肥", "note": "重施氮肥，促进茎叶生长"},
      {"name": "大喇叭口期", "offset": 55, "category": "施肥", "note": "追施穗肥，决定穗粒数关键期"},
      {"name": "病虫害高发期", "offset": 60, "category": "防虫", "note": "重点防玉米螟、黏虫"},
      {"name": "收获期", "offset": 125, "category": "收获", "note": "苞叶变黄、籽粒变硬后收获"}
    ]
  },
  "冬小麦": {
    "type": "粮食作物",
    "zones": {
      "华中": {"sowing_window": "10-01~10-15", "seasons": 1},
      "华北": {"sowing_window": "09-25~10-10", "seasons": 1}
    },
    "stage_offsets_days": [
      {"name": "播种期", "offset": 0, "category": "播种", "note": "适墒播种，深度3-5cm"},
      {"name": "越冬前管理", "offset": 50, "category": "管理", "note": "浇好越冬水，防旱防冻"},
      {"name": "返青期追肥", "offset": 150, "category": "施肥", "note": "返青后及时追施氮肥"},
      {"name": "病虫害防治期", "offset": 170, "category": "防虫", "note": "重点防小麦蚜虫、白粉病"},
      {"name": "灌浆期管理", "offset": 200, "category": "管理", "note": "防干热风，适时灌水"},
      {"name": "收获期", "offset": 230, "category": "收获", "note": "蜡熟末期至完熟期收获"}
    ]
  }
}
```

> **内容建设提示**：这部分数据本质上是"农业常识结构化"，可以和知识库内容建设
> （六大 Agent 实施计划第 4 节）同步推进——写知识库文档时，顺手把关键时间节点
> 提取到这个 JSON 里。

---

## 6. 协作模式扩展

**文件**：`app/agents/skill_router.py`

```python
_COLLABORATION_PATTERNS = {
    # 已有
    ("crop_advisory", "weather"): ["该不该浇水", "现在.*施肥", "今天.*种.*合适"],

    # 新增：极端天气 → 病虫害预警联动
    ("weather", "pest_diagnosis"): ["最近.*多雨.*病", "天气.*会不会.*病虫害"],
}
```

场景示例：用户问"最近一直下雨，我的水稻会不会得病？"——`weather_advice` 先给出
降水预报和暴雨预警，`pest_diagnosis` 补充"持续高湿环境下稻瘟病、纹枯病风险上升，
建议检查叶片"，两个 Skill 的 Playbook 合并执行。

---

## 7. API 与前端（可选直连入口）

与营销模块同样的考虑：除了走对话流程，种植历这类结构化数据更适合做成
独立页面展示。

**文件**：`app/routers/weather.py`（新建，可选）

```python
@router.get("/weather/calendar")
async def get_planting_calendar(field_id: int, user=Depends(get_current_user)):
    field = get_field(field_id)  # 复用现有Field模型，自动取crop和经纬度
    return generate_planting_calendar.invoke({
        "crop": field.current_crop,
        "latitude": field.latitude,
        "longitude": field.longitude,
    })

@router.get("/weather/today-term")
async def get_today_term():
    return solar_term_reminder.invoke({})
```

**前端新增组件**：`frontend-react/src/components/PlantingCalendarTimeline.tsx`

按 `category` 用不同颜色标签展示各阶段（播种=绿/施肥=黄/防虫=红/收获=蓝），
时间轴形式排列，可在地块详情页直接嵌入"查看本地块种植历"入口。

---

## 8. 测试用例

| 测试问题 | 预期路由 | 预期调用工具 |
|---|---|---|
| "成都未来一周天气怎么样" | weather_advice | get_weather_forecast |
| "明天会下大雨吗，我的西瓜要不要做防护" | weather_advice | get_weather_forecast（应触发alerts） |
| "我在黑龙江种玉米，全年该怎么安排" | weather_advice | generate_planting_calendar |
| "现在是什么节气，水稻要注意什么" | weather_advice | solar_term_reminder |
| "最近一直下雨，我的水稻会不会得病" | weather + pest_diagnosis（协作） | get_weather_forecast + 知识库检索 |

验证时重点检查：极端天气场景下 `alerts` 是否真的被 LLM 在回复**开头**提及
（这是 Playbook 中特别强调的一条规则，容易被模型忽略，建议针对性测试）。

---

## 9. 实施阶段与工作量

| 阶段 | 内容 | 工作量 | 依赖 |
|---|---|---|---|
| Phase 1 | analyze_weather_risks + alerts 字段集成 | 1-2 天 | 复用现有天气API |
| Phase 2 | solar_term_reminder + solar_terms.json（核心节气） | 1-2 天 | `cnlunar` 库 |
| Phase 3 | generate_planting_calendar + crop_calendar_templates.json（3-5种作物起步） | 2-3 天 | 作物数据整理 |
| Phase 4（可选） | 独立API路由 + 前端种植历时间轴组件 | 2-3 天 | Phase 3完成 |

**建议顺序**：Phase 1 → Phase 2 → Phase 3，每个阶段都能独立交付可用的功能，
不依赖后续阶段，适合分批测试上线。

---

## 10. 改动文件清单

| 文件 | 操作 |
|---|---|
| `app/skills/definitions/weather_advice/SKILL.md` | 修改：扩展triggers/playbook/allowed_tools |
| `app/tools/weather_risk.py` | 新建：analyze_weather_risks |
| `app/tools/calendar_tools.py` | 新建：solar_term_reminder + generate_planting_calendar |
| `app/schemas/weather.py` | 新建：WeatherAlert / PlantingCalendar 等 Schema |
| `data/solar_terms.json` | 新建：节气提醒数据 |
| `data/crop_calendar_templates.json` | 新建：作物种植历模板 |
| `app/agents/skill_router.py` | 修改：新增 weather+pest_diagnosis 协作模式 |
| `requirements.txt` | 修改：新增 `cnlunar` 依赖 |
| `app/routers/weather.py`（可选） | 新建：独立API入口 |
| `frontend-react/src/components/PlantingCalendarTimeline.tsx`（可选） | 新建：种植历可视化组件 |

---

*本文档为实施参考，具体的天气API响应格式需对照 `app/tools/` 中现有
`get_weather_forecast` 的实现调整字段名称。*
