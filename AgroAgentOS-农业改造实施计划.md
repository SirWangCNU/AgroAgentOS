# AgroAgentOS 农业多智能体协同平台 - 改造实施计划

**版本**: V1.0  
**日期**: 2026-05-28  
**目标**: 将现有 AIOps 智能运维系统改造为面向农业的多智能体协同平台

---

## 一、项目改造总体目标

### 1.1 现状分析

| 模块 | 现状 | 改造后 |
|------|------|--------|
| 品牌定位 | AIOps 智能运维平台 | AgroAgentOS 智农协同平台 |
| Agent 架构 | SkillRouter + Plan-Execute-Replan | 保留架构，重新定义农业技能 |
| 技能库 | 运维诊断技能（CPU/内存/磁盘/进程等） | 农业问答/天气/知识库/营销等 |
| 工具集 | 系统监控 MCP 工具 + 知识库工具 | 天气API + 农业知识库 + 营销生成 |
| 前端界面 | 运维工作台（诊断/告警/可观测性） | 农业工作台（问答/天气/知识/营销） |
| 知识库 | 运维知识库 | 农业种植/病虫害/土壤/气象知识库 |

### 1.2 改造后核心功能

```
┌─────────────────────────────────────────────────────────────┐
│                    AgroAgentOS 智农协同平台                   │
├─────────────┬─────────────┬─────────────┬───────────────────┤
│  农业问答    │  实时天气    │  知识库检索  │  营销内容生成     │
│  (对话Agent) │ (天气Agent) │  (RAG Agent)│  (营销Agent)      │
├─────────────┴─────────────┴─────────────┴───────────────────┤
│                  多智能体调度器 (SkillRouter)                  │
├─────────────────────────────────────────────────────────────┤
│              LangGraph 工作流编排引擎                        │
├─────────────┬─────────────┬─────────────┬───────────────────┤
│  天气MCP    │  农业知识库   │  LLM 推理   │  营销模板引擎     │
│  工具服务    │  (RAG+向量库)│  (多模型)    │                  │
└─────────────┴─────────────┴─────────────┴───────────────────┘
```

---

## 二、分阶段实施计划

### 📋 阶段总览

| 阶段 | 名称 | 核心目标 | 预计周期 |
|------|------|----------|----------|
| Phase 0 | 基础设施重构 | 品牌重命名 + 架构骨架搭建 | 1-2天 |
| Phase 1 | 农业 MVP | 聊天 + 天气 + 基础问答 | 3-5天 |
| Phase 2 | 知识增强 | 文档上传 + RAG检索 + 引用 | 3-5天 |
| Phase 3 | 多Agent协同 | 多技能路由 + 协同调度 | 3-5天 |
| Phase 4 | 营销生成 | AI广告/文案生成Agent | 2-3天 |
| Phase 5 | 前端美化 | 农业工作台UI优化 | 2-3天 |

---

## 三、各阶段详细任务

### Phase 0: 基础设施重构（1-2天）

**目标**: 将现有 AIOps 品牌重构为农业品牌，建立新的项目骨架

#### 任务清单

- [ ] **0.1 项目重命名**
  - 重命名项目标题、Logo、品牌标识
  - 修改 `frontend/index.html` 标题
  - 更新 README.md 为农业主题

- [ ] **0.2 技能模型重构**
  - 修改 `app/skills/models.py`：重新定义农业技能类型
  - 新增技能枚举：`agriculture_qa`, `weather`, `knowledge_base`, `marketing`
  - 修改 `app/skills/registry.py`：注册新的农业技能

- [ ] **0.3 系统提示词重写**
  - 创建 `app/prompts/agriculture_system.py`
  - 定义农业专家人设
  - 定义天气分析师人设
  - 定义营销文案师人设
  - 定义知识库检索员人设

- [ ] **0.4 工具集改造规划**
  - 移除运维相关工具（`get_local_*`, `list_top_processes` 等）
  - 保留 `search_knowledge_base` 和 `get_current_time`
  - 新增天气工具占位

- [ ] **0.5 前端品牌重构**
  - 将侧边栏菜单改为农业主题（首页/智能问答/天气/知识库/营销/历史）
  - 修改颜色主题为农业风格（绿色系）
  - 更新所有"运维"相关文案为"农业"

**交付物**:
- 品牌重命名完成
- 农业技能骨架代码
- 农业系统提示词初版

---

### Phase 1: 农业 MVP（3-5天）

**目标**: 实现基础的农业问答 + 天气显示

#### 1.1 天气模块开发

**新增文件**:
```
app/tools/weather_tool.py         # 天气查询工具
app/services/weather_service.py   # 天气服务（API调用 + 缓存）
mcp_servers/weather_server.py     # 天气MCP服务器
```

**天气API接入方案**:
```python
# 推荐免费天气API
# 1. OpenWeatherMap (免费额度)
# 2. 和风天气 (国内，免费)
# 3. 心知天气 (国内，免费)

# app/services/weather_service.py 核心功能
class WeatherService:
    async def get_current_weather(self, location: str) -> WeatherData:
        """获取当前天气"""
        pass

    async def get_forecast(self, location: str, days: int = 3) -> ForecastData:
        """获取天气预报"""
        pass

    def get_agriculture_advice(self, weather: WeatherData) -> str:
        """根据天气生成农业建议"""
        # 规则引擎：
        # - 降雨概率 > 70% → 不建议喷药
        # - 风速 > 5级 → 不建议喷洒作业
        # - 连续高温 > 35℃ → 提醒增加灌溉
        # - 土壤湿度低 → 建议补水
        pass
```

**天气工具注册**:
```python
@app.tool()
def get_weather(location: str) -> str:
    """获取指定位置的实时天气和农业建议"""
    # 调用 WeatherService
    pass
```

#### 1.2 农业问答 Agent

**修改文件**: `app/agents/skill_router.py`

```python
# 新增农业意图识别
AGRICULTURE_INTENTS = {
    "planting": ["种植", "播种", "栽培", "育苗", "插秧"],
    "fertilization": ["施肥", "肥料", "追肥", "底肥", "复合肥"],
    "pest_control": ["病虫害", "打药", "农药", "虫害", "病害"],
    "irrigation": ["灌溉", "浇水", "排水", "补水"],
    "harvest": ["收获", "采收", "收割", "采摘"],
    "weather": ["天气", "温度", "降雨", "风速", "气象"],
    "marketing": ["广告", "宣传", "文案", "营销", "销售"],
}

def detect_intent(query: str) -> str:
    """检测农业问题意图"""
    for intent, keywords in AGRICULTURE_INTENTS.items():
        if any(kw in query for kw in keywords):
            return intent
    return "general_qa"
```

**农业问答流程**:
```
用户: "现在适合种玉米吗？"
       ↓
SkillRouter (识别为 planting 意图)
       ↓
Planner (制定计划: 1. 查询当地天气 2. 检索玉米种植条件 3. 综合分析)
       ↓
Executor (执行: get_weather("当前位置") + search_knowledge_base("玉米种植条件"))
       ↓
Replanner (评估结果，生成建议)
       ↓
输出: "根据您所在地区天气预报，未来3天有持续降雨，不建议现在播种玉米。建议等..."
```

#### 1.3 前端天气卡片

**修改文件**: `frontend/index.html`

```html
<!-- 新增天气卡片组件 -->
<div class="weather-card">
    <div class="weather-header">
        <i class="fa-solid fa-cloud-sun"></i>
        <span>实时天气</span>
        <span class="weather-location">北京</span>
    </div>
    <div class="weather-body">
        <div class="weather-main">
            <div class="temp">28℃</div>
            <div class="condition">多云</div>
        </div>
        <div class="weather-details">
            <div><i class="fa-solid fa-droplet"></i> 湿度 65%</div>
            <div><i class="fa-solid fa-wind"></i> 风速 3级</div>
            <div><i class="fa-solid fa-cloud-rain"></i> 降雨概率 20%</div>
        </div>
        <div class="agri-advice">
            <i class="fa-solid fa-seedling"></i>
            农业建议：今日适合进行田间作业
        </div>
    </div>
</div>
```

**交付物**:
- 天气查询功能可用
- 农业问答Agent工作正常
- 前端天气卡片展示

---

### Phase 2: 知识增强（3-5天）

**目标**: 实现农业知识库上传、检索和引用

#### 2.1 农业知识库建设

**新增农业知识文档**:
```
knowledge_base/
├── planting/           # 种植技术
│   ├── 水稻种植指南.md
│   ├── 小麦种植技术.md
│   ├── 玉米栽培技术.md
│   └── 蔬菜大棚管理.md
├── pest_control/       # 病虫害防治
│   ├── 常见病虫害图谱.md
│   ├── 农药使用指南.md
│   └── 生物防治方法.md
├── soil/               # 土壤管理
│   ├── 土壤检测与改良.md
│   └── 肥料配方指南.md
└── weather/            # 气象知识
    ├── 农业气象灾害.md
    └── 天气与农事安排.md
```

**知识库导入脚本**:
```python
# scripts/ingest_agriculture_kb.py

async def ingest_agriculture_documents():
    """导入农业知识库"""
    docs_dir = "knowledge_base/"
    for category in ["planting", "pest_control", "soil", "weather"]:
        for file_path in (docs_dir / category).glob("*.md"):
            # 1. 读取文档
            content = file_path.read_text(encoding="utf-8")
            # 2. 按章节切分（保持上下文）
            chunks = split_by_chapter(content, max_chunk_size=500)
            # 3. 向量化存入Milvus
            await embed_and_store(chunks, metadata={"category": category})
```

#### 2.2 RAG 检索增强

**修改文件**: `app/core/hybrid_retriever.py`

```python
class AgricultureRetriever:
    """农业知识库混合检索器"""

    async def search(self, query: str, top_k: int = 5) -> List[Document]:
        """农业知识检索"""
        # 1. 向量检索（语义相似）
        vector_results = await self.vector_search(query, top_k)

        # 2. 关键词检索（精确匹配）
        keyword_results = await self.keyword_search(query, top_k)

        # 3. 混合排序
        combined = self.rrf_merge(vector_results, keyword_results)

        # 4. 重排序
        reranked = await self.reranker.rerank(query, combined)

        return reranked[:top_k]
```

#### 2.3 知识引用展示

**修改前端**: `frontend/index.html`

```html
<!-- 知识引用组件 -->
<div class="knowledge-citation">
    <div class="citation-header">
        <i class="fa-solid fa-book-open"></i>
        <span>知识来源</span>
    </div>
    <div class="citation-body">
        <div class="citation-item">
            <div class="citation-source">《水稻种植指南》第三章</div>
            <div class="citation-content">水稻播种前需要浸种催芽，适宜温度为25-30℃...</div>
            <div class="citation-score">相关度: 92%</div>
        </div>
    </div>
</div>
```

**交付物**:
- 农业知识库建成（至少10篇文档）
- RAG检索功能可用
- 知识引用可展示

---

### Phase 3: 多Agent协同（3-5天）

**目标**: 实现多技能路由和Agent协同调度

#### 3.1 农业技能定义

**修改文件**: `app/skills/models.py`

```python
class AgricultureSkill(str, Enum):
    """农业技能枚举"""
    CROP_QA = "crop_qa"                  # 作物种植问答
    PEST_CONTROL = "pest_control"        # 病虫害诊断
    WEATHER_ADVICE = "weather_advice"    # 天气与农事建议
    SOIL_MANAGEMENT = "soil_management"  # 土壤管理
    IRRIGATION = "irrigation"            # 灌溉建议
    HARVEST = "harvest"                  # 采收指导
    MARKETING = "marketing"              # 营销内容生成
    GENERAL_QA = "general_qa"           # 通用农业问答
```

**技能配置**:
```python
SKILL_CONFIGS = {
    AgricultureSkill.CROP_QA: {
        "name": "作物种植专家",
        "icon": "fa-seedling",
        "description": "提供各类作物的种植技术指导",
        "tools": ["search_knowledge_base", "get_weather"],
        "system_prompt": "你是一位资深农业种植专家，擅长解答各种作物的种植技术问题..."
    },
    AgricultureSkill.PEST_CONTROL: {
        "name": "病虫害防治专家",
        "icon": "fa-bug",
        "description": "诊断病虫害并提供防治方案",
        "tools": ["search_knowledge_base"],
        "system_prompt": "你是一位植物保护专家，能够识别病虫害并给出科学防治建议..."
    },
    AgricultureSkill.WEATHER_ADVICE: {
        "name": "气象农事顾问",
        "icon": "fa-cloud-sun",
        "description": "根据天气条件提供农事建议",
        "tools": ["get_weather", "search_knowledge_base"],
        "system_prompt": "你是农业气象专家，能够根据天气预报给出农事安排建议..."
    },
    # ... 其他技能
}
```

#### 3.2 多Agent调度流程

**修改文件**: `app/agents/skill_router.py`

```python
async def skill_router_node(state: PlanExecuteState) -> dict:
    """农业技能路由器"""
    query = state["user_query"]

    # Step 1: 意图识别
    intent = detect_intent(query)
    logger.info(f"[Router] 检测意图: {intent}")

    # Step 2: 选择技能
    if intent == "weather":
        selected_skill = AgricultureSkill.WEATHER_ADVICE
    elif intent == "pest_control":
        selected_skill = AgricultureSkill.PEST_CONTROL
    elif intent == "marketing":
        selected_skill = AgricultureSkill.MARKETING
    else:
        selected_skill = AgricultureSkill.GENERAL_QA

    # Step 3: 检查是否需要多Agent协同
    if needs_collaboration(query):
        # 例如："明天适合打药吗？" 需要天气 + 病虫害知识
        return {
            "selected_skill": selected_skill,
            "collaboration_skills": ["weather_advice", "pest_control"],
            "pending_reroute": True
        }

    return {"selected_skill": selected_skill}
```

#### 3.3 协同工作流示例

```
用户: "明天适合给苹果树打药吗？"
       ↓
SkillRouter (识别为 pest_control + weather 协同)
       ↓
Planner (制定协同计划):
  Step 1: 获取明天天气预报
  Step 2: 检索苹果树病虫害防治知识
  Step 3: 分析天气对喷药的影响
  Step 4: 综合生成建议
       ↓
Executor:
  - 调用 get_weather("苹果园位置") → 明天有雨
  - 调用 search_knowledge_base("苹果树喷药时间")
  - 分析: 降雨概率80%，风速4级
       ↓
Replanner (汇总结果):
  "根据天气预报，明天有80%降雨概率，不建议喷药。雨水会冲刷药剂，降低防治效果。
   建议等雨后2-3天，叶片干燥后再进行喷药。喷药时注意风速不超过3级..."
```

**交付物**:
- 多技能路由工作正常
- Agent协同调度可用
- 复杂农业问题能综合多源信息

---

### Phase 4: 营销内容生成（2-3天）

**目标**: 实现农产品营销文案和内容生成

#### 4.1 营销Agent开发

**新增文件**: `app/agents/marketing_agent.py`

```python
class MarketingAgent:
    """农产品营销内容生成Agent"""

    MARKETING_TEMPLATES = {
        "douyin": {
            "name": "抖音短视频脚本",
            "format": """
## 标题
{title}

## 开头hook（前3秒）
{hook}

## 正文（30-60秒）
{content}

## 结尾行动号召
{cta}

## 分镜建议
{scenes}
"""
        },
        "xiaohongshu": {
            "name": "小红书图文",
            "format": """
## 标题（20字内，含emoji）
{title}

## 正文
{content}

## 标签
{hashtags}

## 图片建议
{image_suggestions}
"""
        },
        "live_stream": {
            "name": "直播口播稿",
            "format": """
## 开场白（30秒）
{opening}

## 产品介绍（2-3分钟）
{product_intro}

## 卖点强调
{selling_points}

## 互动话术
{interaction}

## 促单话术
{closing}
"""
        }
    }

    async def generate_marketing_content(
        self,
        product_info: dict,
        platform: str,
        style: str = "professional"
    ) -> dict:
        """
        生成营销内容

        Args:
            product_info: {
                "name": "产品名称",
                "origin": "产地",
                "features": ["特点1", "特点2"],
                "price": "价格",
                "target_audience": "目标人群"
            }
            platform: douyin/xiaohongshu/live_stream/wechat
            style: professional/funny/emotional/storytelling
        """
        template = self.MARKETING_TEMPLATES.get(platform)

        prompt = f"""
你是一位农产品营销文案专家。请根据以下产品信息，生成{template['name']}内容。

产品信息：
- 名称：{product_info['name']}
- 产地：{product_info['origin']}
- 特点：{', '.join(product_info['features'])}
- 价格：{product_info['price']}
- 目标人群：{product_info['target_audience']}
- 风格要求：{style}

请按以下格式输出：
{template['format']}
"""
        # 调用LLM生成
        result = await llm.agenerate(prompt)
        return result
```

#### 4.2 营销生成前端

**新增文件**: `frontend/marketing.html` (或集成到主页面)

```html
<!-- 营销生成页面 -->
<div class="page" id="page-marketing">
    <div class="section-title">
        <i class="fa-solid fa-bullhorn"></i>
        <span>AI 营销助手</span>
    </div>

    <div class="marketing-layout">
        <!-- 输入表单 -->
        <div class="marketing-form">
            <div class="form-group">
                <label>产品名称 *</label>
                <input type="text" id="product-name" placeholder="例如：阳澄湖大闸蟹">
            </div>
            <div class="form-group">
                <label>产品特点 *</label>
                <textarea id="product-features" placeholder="每行一个特点"></textarea>
            </div>
            <div class="form-group">
                <label>目标平台</label>
                <select id="target-platform">
                    <option value="douyin">抖音短视频</option>
                    <option value="xiaohongshu">小红书图文</option>
                    <option value="live_stream">直播口播</option>
                    <option value="wechat">朋友圈文案</option>
                </select>
            </div>
            <button class="btn btn-primary" id="generate-marketing">
                <i class="fa-solid fa-wand-magic-sparkles"></i> 生成内容
            </button>
        </div>

        <!-- 生成结果 -->
        <div class="marketing-result">
            <div class="result-header">
                <span>生成结果</span>
                <button class="btn btn-secondary" id="copy-result">
                    <i class="fa-solid fa-copy"></i> 复制
                </button>
            </div>
            <div class="result-body" id="marketing-output">
                <div class="empty-state">
                    <i class="fa-solid fa-bullhorn"></i>
                    <span>填写产品信息后点击生成</span>
                </div>
            </div>
        </div>
    </div>
</div>
```

**交付物**:
- 营销Agent工作正常
- 支持抖音/小红书/直播等多种格式
- 前端营销生成界面可用

---

### Phase 5: 前端美化与优化（2-3天）

**目标**: 完善农业工作台UI，提升用户体验

#### 5.1 农业主题设计

**修改文件**: `frontend/styles.css`

```css
/* 农业主题配色 */
:root {
    --agriculture-primary: #2E7D32;      /* 主色-深绿 */
    --agriculture-secondary: #4CAF50;    /* 次色-中绿 */
    --agriculture-light: #81C784;        /* 浅绿 */
    --agriculture-bg: #F1F8E9;           /* 背景-极浅绿 */
    --agriculture-accent: #FF8F00;       /* 强调-橙色（丰收色）*/
    --agriculture-earth: #795548;        /* 土地棕 */
    --agriculture-sky: #42A5F5;          /* 天空蓝 */
}

/* 侧边栏农业风格 */
.sidebar {
    background: linear-gradient(180deg, #1B5E20 0%, #2E7D32 100%);
}

/* 卡片农业风格 */
.agriculture-card {
    border-left: 4px solid var(--agriculture-primary);
    background: linear-gradient(135deg, #fff 0%, var(--agriculture-bg) 100%);
}
```

#### 5.2 农业工作台布局

**修改文件**: `frontend/index.html`

```html
<!-- 农业工作台三栏布局 -->
<div class="dashboard-grid">
    <!-- 左侧: 智能问答 -->
    <div class="bento-card accent-green">
        <div class="card-title">
            <i class="fa-solid fa-comments"></i> 智能问答
        </div>
        <!-- 聊天界面 -->
    </div>

    <!-- 右上: 天气卡片 -->
    <div class="bento-card accent-blue weather-panel">
        <div class="card-title">
            <i class="fa-solid fa-cloud-sun"></i> 实时天气
        </div>
        <!-- 天气展示 -->
    </div>

    <!-- 右下: 农事建议 -->
    <div class="bento-card accent-orange">
        <div class="card-title">
            <i class="fa-solid fa-lightbulb"></i> 今日农事建议
        </div>
        <!-- 根据天气和季节生成的建议 -->
    </div>

    <!-- 底部: 知识库入口 -->
    <div class="bento-card accent-purple full-width">
        <div class="card-title">
            <i class="fa-solid fa-book-open"></i> 农业知识库
        </div>
        <!-- 热门知识/最近查询 -->
    </div>
</div>
```

#### 5.3 农业图标与插图

**新增文件**:
```
frontend/assets/
├── icons/
│   ├── seedling.svg
│   ├── weather.svg
│   ├── pest.svg
│   ├── harvest.svg
│   └── marketing.svg
└── illustrations/
    ├── farm-scene.svg
    ├── crop-types.svg
    └── weather-agriculture.svg
```

**交付物**:
- 农业主题UI完成
- 三栏工作台布局
- 响应式适配

---

## 四、技术实现要点

### 4.1 天气API接入方案

**推荐方案**: 和风天气API（国内访问快，免费额度足够）

```python
# config.py
WEATHER_API_KEY = os.getenv("QWEATHER_API_KEY")  # 和风天气API Key
WEATHER_API_BASE = "https://devapi.qweather.com/v7"

# app/services/weather_service.py
class QWeatherService:
    """和风天气服务"""

    BASE_URL = "https://devapi.qweather.com/v7"

    async def get_location_id(self, location: str) -> str:
        """获取城市ID"""
        url = f"https://geoapi.qweather.com/v2/city/lookup"
        params = {"location": location, "key": settings.WEATHER_API_KEY}
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, params=params)
            return resp.json()["location"][0]["id"]

    async def get_now_weather(self, location_id: str) -> dict:
        """获取实时天气"""
        url = f"{self.BASE_URL}/weather/now"
        params = {"location": location_id, "key": settings.WEATHER_API_KEY}
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, params=params)
            return resp.json()["now"]
```

### 4.2 知识库切分策略

```python
# app/utils/agriculture_splitter.py
class AgricultureDocumentSplitter:
    """农业文档切分器"""

    def split_by_chapter(self, content: str, max_size: int = 500) -> List[str]:
        """按章节切分，保持上下文"""
        # 1. 按 Markdown 标题分割
        sections = re.split(r'(^#{1,3}\s.*$)', content, flags=re.MULTILINE)

        chunks = []
        current_chunk = ""

        for section in sections:
            if len(current_chunk) + len(section) > max_size:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = section
            else:
                current_chunk += section

        if current_chunk:
            chunks.append(current_chunk.strip())

        return chunks
```

### 4.3 缓存策略

```python
# 天气缓存（15分钟）
WEATHER_CACHE_TTL = 900  # seconds

# 知识库缓存（1小时）
KB_CACHE_TTL = 3600

# 使用 Redis 缓存
import redis.asyncio as redis

class CacheManager:
    def __init__(self):
        self.redis = redis.from_url(settings.REDIS_URL)

    async def get_weather(self, location: str) -> Optional[dict]:
        key = f"weather:{location}"
        data = await self.redis.get(key)
        return json.loads(data) if data else None

    async def set_weather(self, location: str, data: dict):
        key = f"weather:{location}"
        await self.redis.setex(key, WEATHER_CACHE_TTL, json.dumps(data))
```

---

## 五、数据结构设计

### 5.1 农业知识文档表

```sql
CREATE TABLE agriculture_documents (
    id UUID PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    category VARCHAR(50),  -- planting/pest_control/soil/weather
    content TEXT,
    file_path VARCHAR(500),
    chunk_count INTEGER,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

### 5.2 营销任务表

```sql
CREATE TABLE marketing_tasks (
    id UUID PRIMARY KEY,
    user_id UUID,
    product_name VARCHAR(100),
    product_info JSONB,
    platform VARCHAR(50),
    generated_content TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### 5.3 会话历史表

```sql
CREATE TABLE chat_sessions (
    id UUID PRIMARY KEY,
    user_id UUID,
    query TEXT,
    response TEXT,
    agent_type VARCHAR(50),
    weather_info JSONB,
    knowledge_refs JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);
```

---

## 六、API接口设计

### 6.1 聊天接口

```python
# POST /api/v1/chat
{
    "session_id": "uuid",
    "query": "现在适合种玉米吗？",
    "location": "北京",
    "include_weather": true
}

# Response
{
    "session_id": "uuid",
    "response": "根据您所在地区天气预报...",
    "agent": "crop_qa",
    "weather_info": {
        "temperature": 28,
        "humidity": 65,
        "forecast": "明天有雨"
    },
    "knowledge_refs": [
        {
            "source": "玉米种植指南",
            "content": "玉米播种适宜温度...",
            "score": 0.92
        }
    ]
}
```

### 6.2 天气接口

```python
# GET /api/v1/weather?location=北京
{
    "location": "北京",
    "current": {
        "temperature": 28,
        "humidity": 65,
        "wind_speed": 3,
        "condition": "多云"
    },
    "forecast": [...],
    "agriculture_advice": "今日适合田间作业"
}
```

### 6.3 营销生成接口

```python
# POST /api/v1/marketing/generate
{
    "product_name": "阳澄湖大闸蟹",
    "product_info": {
        "origin": "苏州阳澄湖",
        "features": ["个大肥美", "蟹黄饱满", "生态养殖"],
        "price": "198元/盒",
        "target_audience": "25-45岁都市白领"
    },
    "platform": "douyin",
    "style": "funny"
}

# Response
{
    "title": "秋风起，蟹脚痒！阳澄湖大闸蟹来啦！",
    "content": "...",
    "scenes": ["开头:展示大闸蟹特写", "中间:蒸蟹过程", "结尾:品尝画面"]
}
```

---

## 七、风险与应对

| 风险 | 应对措施 |
|------|----------|
| 天气API限流 | 缓存 + 降级到最近一次查询结果 |
| 知识库质量不高 | 优先整理权威农业资料，定期更新 |
| 大模型幻觉 | RAG约束 + 引用来源展示 + 温度调低 |
| 营销内容不专业 | 预设模板 + 风格选项 + 人工审核 |
| 前端性能 | 懒加载 + 流式输出 + 骨架屏 |

---

## 八、验收标准

### 8.1 功能验收

- [ ] 能回答农业种植、病虫害、施肥等常见问题
- [ ] 能显示实时天气并给出农业建议
- [ ] 能上传农业文档并基于知识库回答问题
- [ ] 能生成抖音/小红书/直播等多平台营销内容
- [ ] 能体现多Agent协同（天气+知识库+推理）

### 8.2 性能验收

- [ ] 普通问答响应 < 5秒
- [ ] 天气查询响应 < 2秒
- [ ] 知识库检索响应 < 3秒
- [ ] 营销内容生成 < 10秒

### 8.3 展示验收

- [ ] 页面美观、农业主题突出
- [ ] 三栏工作台布局清晰
- [ ] 天气卡片、知识引用、营销结果展示完整
- [ ] 移动端适配

---

## 九、下一步行动

1. **立即开始 Phase 0**：品牌重命名 + 技能骨架搭建
2. **申请天气API Key**：注册和风天气开发者账号
3. **整理农业知识库**：收集10-20篇高质量农业文档
4. **设计前端原型**：用Figma或纸笔画出农业工作台布局

---

## 附录：文件改动清单

### 需要修改的文件

```
app/
├── agents/
│   ├── graph.py                    # 修改：重命名build_aiops_graph
│   ├── skill_router.py             # 重写：农业意图识别
│   ├── planner.py                  # 修改：农业任务规划
│   └── executor.py                 # 修改：农业工具调用
├── skills/
│   ├── models.py                   # 重写：农业技能定义
│   └── registry.py                 # 重写：农业技能注册
├── tools/
│   ├── mcp_loader.py              # 修改：移除运维工具，添加农业工具
│   └── weather_tool.py            # 新增：天气查询工具
├── services/
│   └── weather_service.py         # 新增：天气服务
├── core/
│   └── hybrid_retriever.py        # 修改：农业知识检索
└── api/v1/
    ├── chat.py                    # 修改：农业问答接口
    └── weather.py                 # 新增：天气接口
    └── marketing.py               # 新增：营销接口

frontend/
├── index.html                     # 重写：农业工作台
├── styles.css                     # 重写：农业主题
└── app.js                         # 修改：农业交互逻辑
```

---

**文档结束**

> 本计划基于现有 AIOps 项目架构，通过渐进式改造实现农业多智能体协同平台。每个阶段都有明确的交付物和验收标准，确保项目可控、可测、可演示。
