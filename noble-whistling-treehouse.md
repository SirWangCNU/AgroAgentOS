# 农场管理增强：地图 + 农机轨迹分析

## Context

当前农场管理模块只有基础的 CRUD（农场/地块的增删改查），经纬度字段虽有但仅是数字输入，无地图展示。需求源于国家农业信息化工程技术研究中心的农机作业监管业务——需要对已导出的历史轨迹 Excel 数据进行本地化管理、地图可视化回放与量化分析。当前版本为离线分析模块，不涉及实时数据接入。

## 技术选型

| 项目 | 选择 | 理由 |
|------|------|------|
| 地图库 | Leaflet.js (CDN) | 免费、轻量(~40KB)、无 API Key、支持多图层切换 |
| 卫星图源 | 高德地图瓦片 | 卫星图+道路图都有，国内覆盖好，免费额度大，需申请 Key |
| Excel 解析 | openpyxl (后端) | 轻量、只读 xlsx 无需额外依赖 |
| 前端图表 | 已有 CSS 柱状图模式 | 不引入 ECharts/Chart.js，保持轻量 |

## 数据模型设计

### 新增表 `trajectory_files` — 轨迹文件元数据

| 列 | 类型 | 说明 |
|----|------|------|
| id | Integer PK | |
| field_id | Integer FK→fields.id | 所属地块 |
| filename | String(256) | 原始文件名 |
| machine_id | String(64) | 农机编号 |
| point_count | Integer | 轨迹点数 |
| start_time | DateTime | 最早 GPS 时间 |
| end_time | DateTime | 最晚 GPS 时间 |
| total_distance_m | Float | 总行驶距离(米) |
| work_distance_m | Float | 作业距离(米) |
| work_area_mu | Float | 作业面积(亩) |
| avg_depth | Float | 平均作业深度 |
| avg_speed | Float | 平均速度 |
| depth_std | Float | 深度标准值 |
| work_width | Float | 幅宽 |
| created_at | DateTime | 导入时间 |

### 新增表 `trajectory_points` — 轨迹点

| 列 | 类型 | 说明 |
|----|------|------|
| id | Integer PK | |
| file_id | Integer FK→trajectory_files.id | 所属轨迹文件 |
| seq | Integer | 序号 |
| gps_time | DateTime | GPS 时间 |
| latitude | Float | 纬度 |
| longitude | Float | 经度 |
| speed | Float | 速度 |
| work_status | String(32) | 工作状态: working/idle/transporting |
| depth | Float | 作业深度 |
| depth_std | Float | 深度标准值 |

> x/y 坐标字段：Excel 中的 x/y 是投影坐标，用于后台面积计算时可选，不在前端展示，暂不入库。如需要可通过经纬度在线计算。

### 现有 Field 表新增列

| 列 | 类型 | 说明 |
|----|------|------|
| boundary_json | Text | 地块边界 GeoJSON（可选，从轨迹自动提取） |

## 文件组织

```
app/models/
  farm.py          # 已有 Farm, Field（新增 boundary_json 列）
  trajectory.py    # 新增 TrajectoryFile, TrajectoryPoint

app/schemas/
  farm.py          # 已有（FieldInfo 新增 boundary_json）
  trajectory.py    # 新增轨迹相关 schema

app/services/
  farm_service.py  # 已有
  trajectory_service.py  # 新增轨迹 CRUD
  trajectory_analysis.py # 新增统计计算

app/api/v1/
  farms.py         # 已有
  trajectories.py  # 新增轨迹 API

frontend/
  farm.js          # 已有（精简）
  farm-map.js      # 新增地图与轨迹可视化
  index.html       # 新增 Leaflet CDN + 页面结构调整
  styles.css       # 新增地图/轨迹相关样式
```

## 后端实现

### 1. 模型层 `app/models/trajectory.py`

```python
TrajectoryFile  # 轨迹文件元数据
TrajectoryPoint # 轨迹点
```

Field 模型新增 `boundary_json = Column(Text, default="")`。

### 2. Schema 层 `app/schemas/trajectory.py`

- `TrajectoryUploadResponse` — 上传结果（文件信息 + 统计概要）
- `TrajectoryFileInfo` — 文件元数据响应
- `TrajectoryPointData` — 单个轨迹点
- `TrajectoryStatsResponse` — 统计分析结果

### 3. 服务层

**`app/services/trajectory_service.py`** (~200行) — 轨迹 CRUD：
- `upload_trajectory(field_id, user_id, file)` — 解析 Excel 并存储
- `get_trajectories(field_id, user_id)` — 列表
- `get_trajectory_points(file_id, user_id)` — 获取轨迹点（用于地图渲染）
- `delete_trajectory(file_id, user_id)` — 删除

**`app/services/trajectory_analysis.py`** (~200行) — 统计计算：
- `calc_distance(points)` — 计算总距离（Haversine 公式）
- `calc_work_area(points, width)` — 作业面积（幅宽 × 作业距离）
- `calc_depth_stats(points)` — 深度统计（均值、合格率）
- `calc_efficiency(points)` — 作业效率（作业时间/总面积）

### 4. API 层 `app/api/v1/trajectories.py`

| Method | Path | 说明 |
|--------|------|------|
| POST | `/fields/{field_id}/trajectories/upload` | 上传轨迹 Excel |
| GET | `/fields/{field_id}/trajectories` | 获取地块的轨迹列表 |
| GET | `/trajectories/{file_id}/points` | 获取轨迹点数据（地图渲染用） |
| GET | `/trajectories/{file_id}/stats` | 获取统计分析 |
| DELETE | `/trajectories/{file_id}` | 删除轨迹 |

### 5. Excel 解析逻辑

预期 Excel 列名映射（中文/英文都兼容）：
- GPS时间 / gps_time → `gps_time`
- 纬度 / lat / latitude → `latitude`
- 经度 / lng / lon / longitude → `longitude`
- 速度 / speed → `speed`
- 工作状态 / work_status / status → `work_status`
- 幅宽 / width → `work_width`
- 作业深度 / depth → `depth`
- 深度标准值 / depth_std → `depth_std`

解析时自动检测列名，支持中英文表头。

## 前端实现

### 1. Leaflet 引入

在 `index.html` 的 `<head>` 中添加：
```html
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
```

图源（高德地图）：
- 高德卫星图：`https://wprd0{s}.is.autonavi.com/appmaptile?x={x}&y={y}&z={z}&lang=zh_cn&size=1&scl=1&style=6`
- 高德道路图：`https://wprd0{s}.is.autonavi.com/appmaptile?x={x}&y={y}&z={z}&lang=zh_cn&size=1&scl=1&style=7`
- OpenStreetMap 作为备用道路图层

> 高德地图免费 Key 需要在 `.env` 中配置 `AMAP_KEY`，瓦片服务本身不强制校验 Key。

### 2. 农场详情页改造

现有农场详情页（`#farm-detail-section`）改为左右布局：
- **左侧**：地图（占 60%），显示地块位置/边界、轨迹叠加
- **右侧**：地块列表 + 轨迹管理面板

### 3. `farm-map.js` 核心功能 (~400行)

```javascript
// 地图初始化
initFarmMap()           // 创建 Leaflet 实例，添加图层切换控件

// 地块定位
showFieldOnMap(field)   // 在地图上标记地块位置
drawFieldBoundary(geojson) // 绘制地块边界

// 轨迹渲染
loadTrajectory(fileId)  // 加载轨迹点
renderTrajectory(points) // 在地图上画轨迹线
colorByStatus(points)   // 按工作状态着色（作业=绿/空闲=灰/转移=蓝）

// 轨迹回放
startPlayback(points)   // 播放轨迹动画
pausePlayback()         // 暂停
setPlaybackSpeed(rate)  // 倍速

// 统计面板
showTrajectoryStats(stats) // 显示统计结果
```

### 4. 地图交互

- 农场创建/编辑时：点击地图选点设置经纬度
- 地块卡片点击：地图飞到该地块位置
- 轨迹导入后：自动在地图上渲染
- 图层切换：卫星/道路一键切换

### 5. 轨迹导入 UI

地块详情中增加"导入轨迹"按钮，触发文件选择 → 上传 → 解析 → 显示结果。
支持拖拽上传 Excel 文件。

### 6. 轨迹回放控制条

地图下方添加播放控制条：
- 播放/暂停按钮
- 进度滑块
- 速度选择（1x/2x/4x）
- 当前时间/位置显示

## 实施步骤（分阶段交付）

> **当前先做 Phase 1+2**，Phase 3+4 后续迭代。

### Phase 1：后端基础（模型 + 轨迹 CRUD）

1. 新增 `app/models/trajectory.py`，定义 TrajectoryFile + TrajectoryPoint
2. Field 模型新增 boundary_json 列
3. 新增 `alembic/versions/004_add_trajectory.py` 迁移
4. 新增 `app/schemas/trajectory.py`
5. 新增 `app/services/trajectory_service.py`（含 Excel 解析）
6. 新增 `app/services/trajectory_analysis.py`（统计计算）
7. 新增 `app/api/v1/trajectories.py`，注册到 main.py
8. requirements.txt 添加 openpyxl

### Phase 2：前端地图基础

1. index.html 添加 Leaflet CDN
2. 新建 `farm-map.js`
3. 改造农场详情页布局（加地图容器）
4. 实现地图初始化 + 图层切换
5. 实现点击地图设置农场/地块坐标
6. main.py 添加 `/farm-map.js` 静态路由

### Phase 3：轨迹可视化

1. 轨迹列表 UI（地块下的轨迹卡片）
2. 轨迹导入（文件上传 + 拖拽）
3. 轨迹线渲染（按状态着色）
4. 轨迹回放控制条
5. 统计分析面板

### Phase 4：地块边界 + 细节打磨

1. 从轨迹自动提取地块边界（凸包算法）
2. 地块边界 GeoJSON 存储/展示
3. 地图上农场→地块的层级导航
4. 样式完善 + 响应式适配

## 验证方式

1. 启动后端 `python -m uvicorn app.main:app --reload`
2. 创建农场时在地图上点击选取坐标
3. 准备测试 Excel 文件（包含 gps_time, latitude, longitude, speed, work_status, depth 列）
4. 在地块中导入轨迹 Excel，验证解析成功
5. 在地图上查看轨迹线渲染（按工作状态着色）
6. 点击播放验证轨迹回放
7. 查看统计分析结果（作业面积、效率、深度合格率）
