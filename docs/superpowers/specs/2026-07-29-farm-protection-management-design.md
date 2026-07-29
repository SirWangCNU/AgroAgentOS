# 农场管理“保收”重构技术规格

## 1. 文档信息

- 项目：AgroAgentOS
- 模块：Web 端农场管理
- 状态：已确认设计，待实施
- 日期：2026-07-29
- 目标用户：需要快速确认农场位置和天气风险的农民

## 2. 背景

当前农场管理页面同时承载农场、地块、轨迹文件、轨迹点、轨迹分析和地图等功能。信息层级多，核心任务不明确，轨迹上传与分析也不是本次“保收”目标所必需。

本次重构把页面聚焦为一个问题：

> 我的农场在哪里，现在的天气是否存在风险？

第一版只提供农场定位、农场与地块档案、实时天气和天气风险。系统不生成病虫害判断、农业行动建议或待办任务。

## 3. 已确认的设计决策

1. 仅设计和实现 Web 端，不包含移动端布局。
2. 支持一个用户管理多个农场，一次只查看一个当前农场。
3. 地图采用“自动定位、手动点击、拖动标记、确认保存”的方式。
4. 不绘制农场或地块边界。
5. 不保留轨迹文件、轨迹点、轨迹分析及相关业务。
6. 显示实时天气和客观天气风险，不提供农业行动建议。
7. 天气数据不写业务数据库，仅使用短期缓存。
8. 删除 `trajectory_points` 和 `trajectory_files` 数据库表。

## 4. 目标与非目标

### 4.1 目标

- 用户进入页面后能立即看到自己的农场列表和地图位置。
- 用户能通过浏览器定位快速找到附近位置，并拖动标记修正农场位置。
- 用户能新增、切换、编辑和删除自己的农场。
- 用户能维护农场下的简单地块档案。
- 用户能查看当前农场的实时天气和天气风险。
- 天气不可用时不影响农场与地图功能。
- 轨迹能力从数据库、后端、前端和用户上下文中完整退役。

### 4.2 非目标

- 移动端、微信小程序或响应式移动布局。
- 地块边界或 GeoJSON 绘制。
- 农机轨迹上传、回放、统计或分析。
- 病虫害风险预测。
- 灌溉、排水、施药等农业行动建议。
- 今日农事、待办、消息推送或预警确认。
- 天气历史、气象图表或农场传感器接入。
- 土壤、生长阶段、播种日期、预计收获日期等精细种植管理。

## 5. Web 页面设计

### 5.1 页面入口

- 路由保持 `/workspace/farms`。
- 导航名称保持“农场管理”。
- 页面标题：`农场管理`
- 页面说明：`查看农场位置与天气风险`
- 页面右上角只保留一个主操作：`新增农场`

### 5.2 桌面布局

页面使用左右两栏地图优先布局：

| 区域 | 宽度 | 内容 |
| --- | --- | --- |
| 左侧信息栏 | 约 320px，固定宽度 | 农场列表、当前农场信息、天气、天气风险、地块列表 |
| 右侧地图 | 占剩余可用宽度 | 农场标记、定位、位置编辑、地图图层切换 |

本期不定义窄屏和移动端重排规则。支持的验收视口以常见桌面宽度为准，最低建议宽度为 1280px。

### 5.3 左侧信息栏

左侧信息栏按以下顺序展示。

#### 农场切换

- 展示农场名称、地址或位置状态、面积。
- 当前农场使用明确的选中态。
- 点击农场后同步更新地图中心、天气和地块列表。
- 农场没有经纬度时显示“位置未设置”，不显示错误地图点。

#### 当前农场

- 名称
- 地址
- 面积（亩）
- 编辑入口
- 删除入口

删除农场前必须提示：删除后，该农场下的地块也会一并删除。

#### 实时天气

只显示：

- 天气状况
- 当前温度
- 湿度
- 风力
- 数据更新时间
- 数据来源

不得显示农业建议字段。

#### 天气风险

每条风险只显示：

- 风险类型，例如暴雨、高温、大风、霜冻
- 风险日期
- 风险等级

无风险时显示“当前未发现明显天气风险”。该文案表示当前预报数据未触发风险规则，不承诺绝对安全。

天气服务未配置、超时或失败时，不显示模拟天气为真实天气。

#### 地块档案

每条地块只显示：

- 地块名称
- 当前作物
- 面积
- 状态：空闲、种植中、休耕

支持新增、编辑和删除地块。不展示轨迹、土壤、生长期、播种日期、预计收获日期或边界信息。

### 5.4 地图区域

地图提供：

- 所有已定位农场的标记。
- 当前农场的突出标记。
- 点击标记切换当前农场。
- “定位到我”按钮。
- “编辑位置”按钮。
- 编辑时允许点击地图放置标记、拖动标记修正位置。
- 位置有未保存变化时显示“保存位置”和“取消”。
- 普通地图与卫星地图切换。

浏览器定位只能由用户点击触发，不在页面加载时自动请求权限。

### 5.5 位置编辑状态

位置编辑必须采用草稿状态，不能在每次拖动时直接写数据库。

状态流如下：

1. 用户点击“编辑位置”。
2. 页面复制当前经纬度到位置草稿。
3. 用户点击“定位到我”、点击地图或拖动标记。
4. 地图只更新草稿标记。
5. 用户点击“保存位置”后才调用更新接口。
6. 保存成功后更新当前农场缓存。
7. 用户点击“取消”时恢复已保存位置。

### 5.6 空状态

#### 用户没有农场

- 地图仍可显示。
- 左侧显示“还没有农场”。
- 主按钮为“创建第一个农场”。

#### 农场没有位置

- 地图显示默认全国视图。
- 左侧天气区域显示“设置农场位置后可查看天气”。
- 地图提供醒目的“定位并设置位置”操作。

#### 农场没有地块

- 显示“暂无地块”。
- 提供“添加地块”操作。

## 6. 视觉方向

界面采用克制的农业工具风格，而不是数据大屏：

- 延续项目现有浅色主题和绿色主色。
- 地图是页面的主要视觉区域。
- 正常天气使用低干扰中性色。
- 只有天气风险使用黄色、橙色或红色等级色。
- 不使用图表、仪表盘、渐变大卡片或装饰性动画。
- 操作按钮使用清晰动词，例如“定位到我”“编辑位置”“保存位置”。
- 删除操作与主要操作保持视觉隔离。

## 7. 数据库设计

业务关系：

`users 1 → N farms 1 → N fields`

### 7.1 `farms`

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | Integer | 主键，自增 | 农场 ID |
| `user_id` | Integer | 外键、非空、索引 | 所属用户 |
| `name` | String(128) | 非空 | 农场名称 |
| `location` | String(256) | 默认空字符串 | 地址或位置标签 |
| `latitude` | Float | 可空 | WGS84 纬度 |
| `longitude` | Float | 可空 | WGS84 经度 |
| `area_mu` | Float | 默认 0 | 面积，单位亩 |
| `description` | Text | 默认空字符串 | 简短备注 |
| `created_at` | DateTime | 非空 | 创建时间 |
| `updated_at` | DateTime | 非空 | 更新时间 |

约束：

- 纬度有效范围为 `[-90, 90]`。
- 经度有效范围为 `[-180, 180]`。
- 面积不得小于 0。
- 所有查询和修改必须同时按 `farm_id` 与当前 `user_id` 校验归属。

### 7.2 `fields`

本期前端和公开请求只使用以下活动字段：

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | Integer | 主键，自增 | 地块 ID |
| `farm_id` | Integer | 外键、非空、索引、级联删除 | 所属农场 |
| `name` | String(128) | 非空 | 地块名称 |
| `area_mu` | Float | 默认 0 | 面积，单位亩 |
| `current_crop` | String(64) | 默认空字符串 | 当前作物 |
| `status` | String(32) | 默认 `idle` | `idle`、`planting`、`fallow` |
| `notes` | Text | 默认空字符串 | 备注 |
| `created_at` | DateTime | 非空 | 创建时间 |
| `updated_at` | DateTime | 非空 | 更新时间 |

现有数据库中的 `soil_type`、`planting_date`、`expected_harvest`、`growth_stage`、`latitude`、`longitude` 和 `boundary_json` 本期不删除，避免产生未经单独批准的地块数据损失；它们不进入新页面的主要交互，也不作为本期新增逻辑的依赖。

### 7.3 不建立天气表

不新增 `farm_weather`、`weather_history` 或 `weather_alerts` 表。

原因：

- 实时天气和预报是外部数据，不是用户业务主数据。
- 本期不需要历史分析、确认状态或消息推送。
- 持久化会引入定时任务、数据过期和清理逻辑。

天气按经纬度使用约 30 分钟 TTL 缓存。缓存键必须对经纬度做有限精度归一化，避免轻微拖动生成大量缓存项。

### 7.4 删除轨迹表

新增 Alembic 迁移：

`alembic/versions/007_remove_trajectory_tables.py`

`down_revision` 指向当前迁移头 `006_add_wx_binding`，不得修改已经存在的 `004_add_trajectory.py`。

升级顺序：

1. 删除 `ix_trajectory_points_file_id`。
2. 删除 `trajectory_points`。
3. 删除 `ix_trajectory_files_field_id`。
4. 删除 `trajectory_files`。

降级顺序：

1. 重建 `trajectory_files` 空表和索引。
2. 重建 `trajectory_points` 空表和索引。

降级只能恢复表结构，不能恢复轨迹数据。迁移执行前必须备份生产数据库。

本期不通过该迁移删除 `fields.boundary_json`，因为该列与轨迹表删除不是同一个数据丢失决策。

## 8. 坐标系统

数据库统一保存 WGS84 坐标，因为浏览器 Geolocation 和天气接口均以该坐标为标准输入。

当前普通地图使用 OpenStreetMap，与 WGS84 存储兼容。当前高德卫星瓦片使用 GCJ-02，直接叠加 WGS84 标记会在中国境内产生偏移。

本期采用统一坐标方案：普通和卫星图层均改用与 WGS84/Web
Mercator 兼容的瓦片源，不继续使用当前高德卫星瓦片。数据库、浏览器定位、
地图标记和天气接口全部使用 WGS84，不引入 GCJ-02 转换逻辑。

## 9. API 设计

现有农场和地块 CRUD 路径保持不变。

### 9.1 农场列表

`GET /api/v1/farms?page=1&page_size=100`

返回当前用户的农场。`field_count` 可以由服务层计算，不在数据库冗余存储。

### 9.2 农场详情

`GET /api/v1/farms/{farm_id}`

返回当前用户的农场和地块。非所属农场返回统一的资源不存在或无权限错误，不泄露其他用户资源是否存在。

### 9.3 更新农场及位置

`PUT /api/v1/farms/{farm_id}`

继续使用现有更新接口。位置保存提交：

```json
{
  "latitude": 36.123456,
  "longitude": 118.123456,
  "location": "山东省某市某县"
}
```

服务端必须校验经纬度范围。`location` 可由用户填写或使用已有位置标签；本期不强制新增反向地理编码服务。

### 9.4 农场天气聚合接口

新增：

`GET /api/v1/farms/{farm_id}/weather`

职责：

1. 校验当前用户对农场的访问权。
2. 校验农场存在有效经纬度。
3. 查询实时天气。
4. 查询天气风险。
5. 过滤农业建议字段。
6. 返回数据来源和更新时间。

响应结构：

```json
{
  "code": "SUCCESS",
  "message": "农场天气查询成功",
  "data": {
    "available": true,
    "current": {
      "condition": "多云",
      "temperature": 28,
      "humidity": 65,
      "wind_speed": 3.2,
      "wind_level": 3,
      "update_time": "2026-07-29T10:00:00+08:00"
    },
    "alerts": [
      {
        "alert_type": "高温",
        "date": "2026-07-30",
        "severity": "中"
      }
    ],
    "source": "qweather"
  }
}
```

接口不得返回 `agriculture_advice` 或天气风险内部的 `advice`。

当服务只得到 Mock 数据时，农场页面接口返回 `available: false` 和明确的不可用原因，不把 Mock 数值作为实时数据返回。

### 9.5 删除的轨迹接口

以下接口全部删除，不提供兼容代理：

- `GET /api/v1/fields/{field_id}/trajectories`
- `POST /api/v1/fields/{field_id}/trajectories/upload`
- `GET /api/v1/trajectories/{file_id}/points`
- `GET /api/v1/trajectories/{file_id}/stats`
- `GET /api/v1/trajectories/{file_id}/analysis`
- `DELETE /api/v1/trajectories/{file_id}`

## 10. 前端状态与数据流

### 10.1 React Query

查询键：

- `["farms"]`
- `["farm", farmId]` 或沿用 `["fields", farmId]`
- `["farm-weather", farmId]`

天气查询只在以下条件满足时启用：

- 已选择农场。
- 农场存在合法经纬度。

切换农场时，旧农场天气可以保留在 React Query 缓存中，但界面不得把旧数据显示在新农场下。

### 10.2 页面本地状态

页面只保留：

- `selectedFarmId`
- `isLocationEditing`
- `draftPosition`
- 农场和地块弹窗状态

删除：

- `selectedFieldId` 的轨迹用途
- `selectedFileId`
- `trajectoryPoints`
- `showAnalysis`
- 轨迹上传弹窗状态

### 10.3 保存位置

- 拖动只更新 `draftPosition`。
- 保存成功后使 `["farms"]` 和当前农场详情失效并重新获取。
- 保存失败时保留草稿标记，显示错误并允许重试。
- 取消时清空草稿并恢复原位置。

## 11. 后端分层

### API 层

- `app/api/v1/farms.py` 负责请求参数、当前用户、调用服务和组装 `ApiResponse`。
- 路由不得直接实现天气调用规则或数据库查询。

### Service 层

- `farm_service` 负责农场归属校验和农场/地块业务。
- `weather_service` 负责天气提供方、坐标查询、缓存和风险查询。
- 可增加一个小型聚合服务函数，用农场坐标组装页面需要的天气摘要。

### Schema 层

- 在 `app/schemas/weather.py` 定义农场天气响应结构。
- 前端在 `frontend-react/src/types/weather.ts` 定义对应类型。
- 响应中不包含农业建议字段。

## 12. 轨迹退役范围

### 12.1 删除文件

- `app/api/v1/trajectories.py`
- `app/models/trajectory.py`
- `app/schemas/trajectory.py`
- `app/services/trajectory_service.py`
- `app/services/user_context/trajectory_context.py`
- `frontend-react/src/components/farm/TrajectoryAnalysis.tsx`
- `scripts/test_trajectory.py`
- `tests/services/user_context/test_trajectory_context.py`

### 12.2 修改文件

- `app/main.py`：删除轨迹路由导入与注册。
- `app/core/redis.py`：删除只服务于轨迹点的缓存键和读写方法。
- `app/services/user_context/intent.py`：删除轨迹意图字段、关键词和识别分支。
- `app/services/user_context/service.py`：删除轨迹上下文注入。
- `app/runtime/agent_harness.py`：删除轨迹数据说明。
- `app/models/__init__.py` 或其他模型注册位置：删除轨迹模型注册。
- `scripts/migrate_sqlite_to_mysql.py`：删除轨迹表迁移逻辑。
- `frontend-react/src/api/farms.ts`：删除所有轨迹 API 函数。
- `frontend-react/src/types/farm.ts`：删除轨迹类型。
- `frontend-react/src/pages/Farms.tsx`：重写为地图、农场、天气和地块页面。
- `frontend-react/src/components/map/FarmMap.tsx`：删除轨迹点绘制逻辑，增加位置编辑能力。
- `frontend-react/src/pages/Dashboard.tsx`：把“农场、地块与作业轨迹”改为“农场位置与天气风险”。
- 相关用户上下文测试：删除轨迹断言，保留农场上下文测试。
- 架构和跨模块文档：删除仍把轨迹描述为现行能力的内容。

实施前应再次使用全仓搜索确认没有遗漏：

```powershell
rg -n -S "TrajectoryFile|TrajectoryPoint|trajectory_files|trajectory_points|trajectory|轨迹" app frontend-react tests scripts
```

保留历史 Alembic 迁移 `004_add_trajectory.py`，因为新数据库仍需能够从历史版本按顺序升级到最新状态。

## 13. 天气失败与错误处理

| 场景 | 页面行为 |
| --- | --- |
| 农场无经纬度 | 提示先设置农场位置，不发天气请求 |
| 浏览器不支持定位 | 保留手动点击地图设置位置 |
| 用户拒绝定位权限 | 提示可手动设置，不重复弹出权限请求 |
| 定位超时 | 保留位置编辑状态，允许重试或手动设置 |
| 天气 API 超时 | 天气区域单独显示暂不可用，地图和 CRUD 正常 |
| 天气 API 未配置 | 显示“天气服务未配置”，不显示 Mock 数值 |
| 天气无风险 | 显示“当前未发现明显天气风险” |
| 保存位置失败 | 保留草稿位置并允许重试 |
| 农场被其他请求删除 | 清除当前选择并重新获取农场列表 |

## 14. 安全与数据边界

- 所有农场与地块接口必须使用当前登录用户。
- 不能仅凭 `farm_id` 或 `field_id` 修改资源。
- 浏览器定位仅用于当前用户主动设置农场位置。
- 前端日志不得输出完整认证信息。
- 天气提供方密钥只存在后端配置，不能进入前端构建。
- 删除农场和执行轨迹删除迁移均属于破坏性操作，必须有明确确认或备份流程。

## 15. 实施顺序

### 阶段 0：备份和基线

1. 检查工作区状态。
2. 记录当前 Alembic 版本。
3. 备份数据库。
4. 运行相关基线测试和前端构建，区分既有问题。

SQLite 默认数据库备份示例：

```powershell
Copy-Item -LiteralPath .\data\agro_agent.db -Destination .\data\agro_agent.before-farm-refactor.db
alembic current
```

MySQL 应使用项目部署环境的标准备份流程或 `mysqldump`，不得在未备份时执行删除表迁移。

### 阶段 1：后端轨迹退役

1. 新增删除轨迹表的 Alembic 迁移。
2. 删除轨迹 API、Schema、Service 和 ORM。
3. 从 `app/main.py` 移除路由。
4. 删除 Redis 轨迹缓存逻辑。
5. 删除用户上下文中的轨迹依赖。
6. 更新受影响的测试、脚本和文档。

### 阶段 2：农场天气聚合

1. 定义精简天气响应 Schema。
2. 在服务层实现按农场位置查询天气和风险。
3. 新增农场天气接口。
4. 明确 Mock、超时和无位置响应。
5. 增加归属校验与服务测试。

### 阶段 3：Web 页面重构

1. 删除轨迹 API 和 TypeScript 类型。
2. 重写农场页面状态。
3. 重写地图组件，加入位置草稿、定位、拖动和保存。
4. 实现左侧农场、天气、风险和地块区域。
5. 完成加载、空数据、错误和保存状态。
6. 更新 Dashboard 中的模块说明。

### 阶段 4：迁移与验证

1. 在备份副本或测试数据库执行升级。
2. 验证轨迹表不存在。
3. 验证农场与地块数据仍存在。
4. 运行后端测试。
5. 运行前端 lint 和生产构建。
6. 启动应用进行桌面 Web 交互检查。

## 16. 执行命令

### 安装依赖

本设计不要求新增前后端依赖。使用现有依赖：

```powershell
pip install -r requirements.txt
Set-Location .\frontend-react
npm ci
Set-Location ..
```

### 数据库迁移

```powershell
alembic current
alembic upgrade head
alembic current
```

检查 SQLite 表：

```powershell
@'
import sqlite3

conn = sqlite3.connect("data/agro_agent.db")
tables = {
    row[0]
    for row in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )
}
assert "farms" in tables
assert "fields" in tables
assert "trajectory_files" not in tables
assert "trajectory_points" not in tables
print("migration check passed")
'@ | python -
```

### 后端测试

实施时新增 `tests/services/test_farm_service.py` 和
`tests/services/test_farm_weather.py`。先运行直接相关测试：

```powershell
pytest tests/services/test_farm_service.py tests/services/test_farm_weather.py
```

再运行全量测试：

```powershell
pytest
```

### 前端检查

```powershell
Set-Location .\frontend-react
npm run lint
npm run build
Set-Location ..
```

### 本地启动

```powershell
uvicorn app.main:app --reload --port 9800
```

另一个终端：

```powershell
Set-Location .\frontend-react
npm run dev
```

浏览器打开 `/workspace/farms`，使用桌面视口验证。

## 17. 测试设计

### 17.1 后端

- 用户只能列出自己的农场。
- 用户不能查看、修改或删除其他用户的农场。
- 农场经纬度范围校验正确。
- 删除农场级联删除地块。
- 无位置农场的天气接口返回明确不可用状态。
- 有位置农场调用坐标天气查询。
- Mock 天气不作为真实数据返回。
- 天气服务异常被转换为稳定响应，不导致农场接口整体失败。
- 农场天气响应不含 `agriculture_advice` 和 `advice`。
- Alembic 升级后轨迹表消失。
- Alembic 降级能重建空轨迹表。
- 用户上下文仍能注入农场和地块信息，但不再识别或注入轨迹。

### 17.2 前端

- 无农场、无位置、无地块都有正确空状态。
- 多农场点击切换地图、天气和地块。
- 定位成功后出现草稿标记。
- 定位拒绝后仍可点击地图放置标记。
- 拖动标记不立即写数据库。
- 保存成功后退出编辑状态并刷新数据。
- 保存失败后保留草稿位置。
- 取消位置编辑恢复原标记。
- 天气加载、无风险、失败和未配置状态可区分。
- 页面没有轨迹上传、轨迹点或轨迹分析入口。

### 17.3 手工桌面验收

至少使用以下视口：

- 1440 × 900
- 1280 × 720

检查：

- 左侧约 320px，地图占据主要区域。
- 页面无横向滚动。
- 地图控件不覆盖保存按钮。
- 风险颜色不影响文本可读性。
- 键盘可聚焦主要按钮。
- 浏览器定位权限请求只由用户操作触发。

## 18. 验收标准

全部满足后才能交付：

1. `/workspace/farms` 只包含农场、地块、地图和天气风险。
2. 支持多个农场并能从列表或地图切换。
3. 支持定位、点击地图、拖动标记、保存和取消位置编辑。
4. 农场位置以 WGS84 存储，地图显示无明显坐标偏移。
5. 有位置时显示真实天气；无位置或天气不可用时显示明确状态。
6. 页面和农场天气接口不包含农业行动建议。
7. `trajectory_points` 和 `trajectory_files` 已通过新迁移删除。
8. 应用代码不再注册或引用轨迹 API、模型、服务和前端组件。
9. 农场与地块现有数据在迁移后仍保留。
10. 后端测试、前端 lint 和前端生产构建通过。
11. 技术文档、API 描述和架构说明与实现同步。

## 19. 交付物

- 本技术规格文档。
- 详细实施计划。
- Alembic 删除轨迹表迁移。
- 重构后的 FastAPI 农场与天气接口。
- 重构后的 React Web 农场管理页面。
- 更新后的测试。
- 更新后的架构和 API 文档。
- 验证结果与数据库备份说明。

## 20. 已知限制

- 本期没有天气历史或消息推送。
- 天气风险依赖外部天气服务和现有风险规则，不等同于官方灾害承诺。
- 农场地址本期可以人工维护，不强制接入反向地理编码。
- 地块的历史扩展字段仍保留在数据库中，但不进入新页面主要流程。
- 轨迹迁移删除的数据无法通过 Alembic 降级恢复，只能从备份恢复。
