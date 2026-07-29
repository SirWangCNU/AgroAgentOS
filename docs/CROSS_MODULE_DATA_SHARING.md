# 智能问答跨模块数据共享方案（历史归档）

> 状态：本文件记录了早期“轨迹作业数据接入问答”的设计。自 2026-07-29 起，`trajectory_files`、`trajectory_points` 及轨迹功能已从系统退役；文中所有轨迹相关表、接口、缓存和上下文注入说明均不再适用于当前实现，也不得据此恢复该能力。

> 目标：让智能问答（RAG Copilot）能够检索并引用用户在农场管理、轨迹作业、营销助手、病虫害诊断等模块中产生的数据，实现"用户昨天导入了某地块的作业数据，今天在问答中就能分析"的体验。

---

## 一、现状分析

### 1.1 已有的跨模块集成

| 集成路径 | 机制 | 局限 |
|----------|------|------|
| AIOps诊断报告 → RAG Chat | Redis共享列表 `rag:diagnosis:reports` | 仅最近几条，无结构化检索 |
| RAG Chat/AIOps → 历史记录 → 知识库 | SQLite `history_records` + 手动上传Milvus | 需用户手动触发 |
| Farm → Field → Trajectory | 数据库外键关联 | 问答系统无法直接访问 |

### 1.2 核心缺口

1. **农场/地块数据**：问答系统不知道用户有哪些农场、地块、当前种了什么
2. **轨迹作业数据**：用户上传的作业数据（深度、面积、效率）对问答不可见
3. **营销任务记录**：历史营销内容无法被问答检索
4. **病虫害诊断记录**：历史诊断结果散落在不同存储中
5. **缺乏统一的用户数据索引**：各模块数据孤立，没有面向问答的聚合层

---

## 二、总体架构设计

### 2.1 架构概览

```
┌─────────────────────────────────────────────────────────────┐
│                    用户提问（智能问答）                         │
│                     POST /api/v1/chat/stream                 │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│              RAG Chat Pipeline (rag_service.py)              │
│                                                             │
│  1. 加载会话记忆 (Redis)                                      │
│  2. 查询改写 (LLM)                                           │
│  3. ★ 用户数据上下文注入 (NEW) ◄──────────────────────┐       │
│  4. 知识库检索 (Milvus Vector + BM25 + Reranker)       │       │
│  5. Web搜索 (可选)                                      │       │
│  6. LLM生成回答                                        │       │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│            ★ UserContextService (新增核心服务)                 │
│                                                             │
│  聚合用户在各模块的数据，生成结构化上下文摘要                      │
│                                                             │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐       │
│  │ 农场管理  │ │ 轨迹作业  │ │ 营销助手  │ │ 病虫害   │       │
│  │ Farm     │ │ Traject  │ │ Market   │ │ Pest     │       │
│  │ Service  │ │ Service  │ │ Service  │ │ Service  │       │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘       │
│       │            │            │            │              │
│       ▼            ▼            ▼            ▼              │
│  ┌──────────────────────────────────────────────────┐       │
│  │              SQLite (统一数据源)                    │       │
│  │  farms / fields / trajectory_files /              │       │
│  │  marketing_tasks / pest_diagnoses /               │       │
│  │  history_records                                  │       │
│  └──────────────────────────────────────────────────┘       │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 核心思路

**不做数据迁移，做数据索引与摘要注入。** 各模块数据仍存储在原有表中，新增一个 `UserContextService` 负责：

1. 根据用户提问的意图，**按需检索**相关模块数据
2. 将检索结果**格式化为结构化文本摘要**
3. 将摘要**注入到 LLM 的 system prompt 或 context 中**

---

## 三、详细设计

### 3.1 新增服务：UserContextService

**文件位置**：`app/services/user_context.py`

**职责**：聚合用户各模块数据，根据查询意图生成上下文摘要。

```python
class UserContextService:
    """聚合用户各模块数据，为智能问答提供上下文。"""

    def __init__(self, db: Session, user_id: int):
        self.db = db
        self.user_id = user_id

    async def get_context(self, query: str) -> str:
        """根据用户查询，返回相关模块数据的结构化摘要。"""
        context_parts = []

        # 1. 基础用户画像（农场概况）
        farm_summary = self._get_farm_summary()
        if farm_summary:
            context_parts.append(farm_summary)

        # 2. 根据查询意图检索特定模块数据
        intent = self._detect_intent(query)

        if intent.has_farm_intent:
            context_parts.append(self._get_farm_detail(intent.farm_keywords))

        if intent.has_trajectory_intent:
            context_parts.append(self._get_trajectory_context(intent.time_range))

        if intent.has_pest_intent:
            context_parts.append(self._get_pest_history())

        if intent.has_marketing_intent:
            context_parts.append(self._get_marketing_history())

        return "\n\n".join(context_parts)
```

### 3.2 意图识别层

**方案选择：轻量关键词匹配 + 规则判断**（不额外调用LLM，降低延迟）

```python
@dataclass
class QueryIntent:
    has_farm_intent: bool = False       # "农场"、"地块"、"种植"、"土壤"
    has_trajectory_intent: bool = False  # "作业"、"轨迹"、"深度"、"面积"、"效率"
    has_pest_intent: bool = False        # "病虫害"、"虫害"、"病害"、"诊断"
    has_marketing_intent: bool = False   # "营销"、"推广"、"销售"、"文案"
    farm_keywords: list[str] = None      # 匹配到的农场/地块名称
    time_range: tuple = None             # 时间范围（如有）

# 意图关键词映射
INTENT_KEYWORDS = {
    "farm": ["农场", "地块", "种植", "土壤", "作物", "生长", "播种", "收获", "田块"],
    "trajectory": ["作业", "轨迹", "深度", "面积", "效率", "机械", "农机", "作业数据", "作业质量"],
    "pest": ["病虫害", "虫害", "病害", "诊断", "打药", "农药", "防治", "发病"],
    "marketing": ["营销", "推广", "销售", "文案", "宣传", "品牌", "客户"],
}
```

**进阶方案（Phase 2）**：在查询改写阶段让 LLM 同时输出意图标签，零额外延迟（复用已有LLM调用）。

### 3.3 各模块数据检索方法

#### 3.3.1 农场概况摘要（默认注入）

每次问答都注入，让 LLM 知道用户的基本情况：

```
【用户农场概况】
- 农场数量：2个
  - 阳光农场（山东寿光，50亩）：3个地块
    · A1地块：小麦，播种期，50亩，壤土
    · A2地块：玉米，生长期，30亩，黏土
    · A3地块：休耕中
  - 绿源农场（河南新乡，80亩）：2个地块
    · B1地块：水稻，分蘖期，40亩
    · B2地块：大棚蔬菜（番茄），结果期，5亩
```

**实现**：查询 `farms` + `fields` 表，按 `user_id` 过滤，拼接摘要文本。数据量小（通常 <20 条），全量注入。

#### 3.3.2 轨迹作业数据（按需注入）

当用户提到"作业"、"数据"、"深度"等关键词时触发：

```
【近期作业数据】
- A1地块 近期作业记录：
  · 2026-05-28 旋耕作业：面积48.5亩，平均深度18.2cm，深度标准差2.1cm，
    平均速度4.2km/h，作业效率92%，机手编号JD-1001
  · 2026-05-15 播种作业：面积49.0亩，平均深度5.0cm，...
- 数据来源：用户于2026-05-28上传的Excel文件
```

**实现**：
1. 查询 `trajectory_files` + `fields` + `farms` 表，获取用户的轨迹文件列表
2. 按时间倒序取最近 N 条（默认5条）
3. 从 `trajectory_files` 表的统计字段（`work_area_mu`, `avg_depth`, `depth_std`, `avg_speed`）直接构建摘要
4. 不需要查询 `trajectory_points`（数万条GPS点），只用聚合统计值

```python
def _get_trajectory_context(self, time_range=None) -> str:
    query = (
        self.db.query(TrajectoryFile, Field, Farm)
        .join(Field, TrajectoryFile.field_id == Field.id)
        .join(Farm, Field.farm_id == Farm.id)
        .filter(Farm.user_id == self.user_id)
        .order_by(TrajectoryFile.start_time.desc())
    )
    if time_range:
        query = query.filter(TrajectoryFile.start_time >= time_range[0])
    records = query.limit(5).all()

    if not records:
        return ""

    lines = ["【近期作业数据】"]
    for tf, field, farm in records:
        lines.append(
            f"- {farm.name}/{field.name} {tf.start_time:%Y-%m-%d} 作业记录：\n"
            f"  文件：{tf.filename}，机具：{tf.machine_id or '未知'}\n"
            f"  面积：{tf.work_area_mu:.1f}亩，"
            f"平均耕深：{tf.avg_depth:.1f}cm（标准差{tf.depth_std:.1f}cm），"
            f"平均速度：{tf.avg_speed:.1f}km/h，"
            f"作业距离：{tf.work_distance_m/1000:.1f}km"
        )
    return "\n".join(lines)
```

#### 3.3.3 病虫害诊断历史（按需注入）

```
【近期病虫害诊断记录】
- 2026-05-25 B1地块（水稻）：疑似稻飞虱，置信度85%
  建议：使用吡虫啉喷雾防治，注意田间排水
- 2026-05-10 A1地块（小麦）：小麦条锈病，置信度92%
  建议：三唑酮喷雾，7天后复查
```

**实现**：查询 `pest_diagnoses` 表（或 `history_records` 中 `source='aiops'` + `skill='pest_diagnosis'` 的记录）。

#### 3.3.4 营销任务历史（按需注入）

```
【近期营销内容】
- 2026-05-20 为"阳光农场有机番茄"生成的营销文案：
  主题：自然熟透，阳光味道 | 渠道：微信朋友圈
  核心卖点：有机认证、自然成熟、48小时产地直发
```

**实现**：查询 `marketing_tasks` 表。

### 3.4 集成到 RAG Chat Pipeline

修改 `app/services/rag_service.py` 的 `stream_chat()` 函数，在检索阶段注入用户上下文：

```python
async def stream_chat(user_id: int, session_id: str, message: str, ...):
    # ... 现有步骤1-2（加载会话、查询改写）...

    # ★ 新增：用户数据上下文注入
    user_context_svc = UserContextService(db, user_id)
    user_context = await user_context_svc.get_context(rewritten_query)

    # 现有步骤3：知识库检索
    kb_results = await advanced_search(rewritten_query, ...)

    # 构建增强的 system prompt
    system_prompt = build_system_prompt(
        kb_context=kb_results,
        user_context=user_context,      # ★ 新增参数
        diagnosis_report=recent_report,
    )

    # ... 后续LLM生成步骤不变 ...
```

### 3.5 System Prompt 增强

在 system prompt 模板中增加用户数据引用指引：

```
你是智农协同平台的农业智能助手。除了知识库资料外，你还拥有以下关于该用户的实际农场数据：

{user_context}

使用规则：
1. 当用户的问题涉及自己的农场、地块、作业数据时，优先引用上述用户数据
2. 将用户实际数据与知识库理论知识结合，给出针对性建议
3. 引用用户数据时注明来源，如"根据您5月28日上传的A1地块作业数据..."
4. 如果用户数据与知识库建议存在矛盾（如作业深度偏大），主动指出并分析原因
5. 不要编造用户不存在的数据
```

---

## 四、数据流转全景

### 4.1 典型用户场景

**场景：用户昨天导入了A1地块的旋耕作业数据，今天问"我A1地块的旋耕深度合适吗？"**

```
用户提问
  │
  ▼
查询改写 → "A1地块旋耕深度是否合适"（消除指代）
  │
  ▼
意图识别 → farm_intent=True, trajectory_intent=True
  │
  ├─► 农场上下文 → "A1地块：小麦，播种期，壤土"
  │
  ├─► 轨迹上下文 → "A1地块 5/28 旋耕：深度18.2cm，标准差2.1cm"
  │
  ├─► 知识库检索 → "小麦旋耕深度建议15-20cm，壤土适中..."
  │
  ▼
LLM综合生成：
  "根据您5月28日上传的A1地块作业数据，旋耕平均深度为18.2cm，
   标准差2.1cm。结合知识库中小麦播种前旋耕的建议深度（15-20cm），
   您的作业深度处于合理范围内。标准差较小说明作业质量均匀。
   建议播种前再浅旋一次（5-8cm）以整地保墒。"
```

### 4.2 数据流向图

```
┌──────────────┐    写入     ┌──────────────┐
│  农场管理页面  │──────────►│ farms 表     │
│  frontend    │           │ fields 表    │
└──────────────┘           └──────┬───────┘
                                  │
┌──────────────┐    写入          │ 读取
│  轨迹上传页面  │──────────►┌─────┴───────┐
│  frontend    │           │ trajectory  │    聚合
└──────────────┘           │ files 表    │──────────┐
                           └─────────────┘          │
┌──────────────┐    写入                            ▼
│  营销助手页面  │──────────►┌─────────────┐  ┌──────────────┐
│  frontend    │           │ marketing   │  │ UserContext  │
└──────────────┘           │ tasks 表    │──►│ Service     │
                           └─────────────┘  │ (新增)       │
┌──────────────┐    写入                    │              │
│  病虫害诊断   │──────────►┌─────────────┐  │  按意图检索   │
│  AIOps       │           │ pest_diag   │──►│  格式化摘要   │
│              │           │ history_rec │  └──────┬───────┘
└──────────────┘           └─────────────┘         │
                                                    │ 注入context
                                                    ▼
                                            ┌──────────────┐
                                            │  RAG Chat    │
                                            │  智能问答     │
                                            │  LLM 生成    │
                                            └──────────────┘
```

---

## 五、实现步骤（分阶段）

### Phase 1：基础数据注入（1-2天）

**目标**：智能问答能感知用户的农场和地块信息。

| 步骤 | 文件 | 内容 |
|------|------|------|
| 1 | `app/services/user_context.py` (新建) | 实现 `UserContextService`，包含 `_get_farm_summary()` |
| 2 | `app/services/rag_service.py` | 在 `stream_chat()` 中调用 `UserContextService`，注入农场概况 |
| 3 | `app/prompts/system_prompt.txt` | 增加用户数据引用指引 |

**验收标准**：用户问"我种了什么"，能准确回答出所有农场和地块的作物信息。

### Phase 2：轨迹数据接入（1天）

**目标**：智能问答能检索和分析用户的作业数据。

| 步骤 | 文件 | 内容 |
|------|------|------|
| 1 | `app/services/user_context.py` | 实现 `_get_trajectory_context()` |
| 2 | `app/services/user_context.py` | 实现 `_detect_intent()` 意图识别 |
| 3 | `app/services/rag_service.py` | 按需注入轨迹上下文 |

**验收标准**：用户问"A1地块最近作业质量怎么样"，能引用具体的深度、面积、效率数据。

### Phase 3：营销与病虫害历史接入（1天）

| 步骤 | 文件 | 内容 |
|------|------|------|
| 1 | `app/services/user_context.py` | 实现 `_get_pest_history()` 和 `_get_marketing_history()` |
| 2 | `app/services/rag_service.py` | 按需注入诊断和营销历史 |

**验收标准**：用户问"上次那个番茄病害怎么处理的"，能引用诊断记录和建议。

### Phase 4：会话级数据卡片（前端增强，2天）

**目标**：在问答界面展示引用的数据来源卡片，提升可信度。

```
┌─────────────────────────────────────────────────┐
│ 🤖 根据您5月28日上传的A1地块作业数据...           │
│                                                  │
│ ┌─ 引用数据 ─────────────────────────────────┐   │
│ │ 📊 A1地块旋耕作业 (2026-05-28)              │   │
│ │    面积 48.5亩 | 深度 18.2±2.1cm            │   │
│ │    速度 4.2km/h | [查看详情]                 │   │
│ └────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────┘
```

| 步骤 | 文件 | 内容 |
|------|------|------|
| 1 | `app/services/rag_service.py` | 在SSE流中输出引用数据的结构化标记 |
| 2 | `frontend/app.js` | 解析标记，渲染数据卡片 |
| 3 | `frontend/styles.css` | 数据卡片样式 |

### Phase 5：智能上下文缓存优化（可选）

当用户数据量增大时，避免每次都查数据库：

| 步骤 | 内容 |
|------|------|
| 1 | 农场概况缓存到Redis（TTL 30min，农场变更时主动失效） |
| 2 | 最近轨迹摘要缓存到Redis（TTL 1h，新上传时主动失效） |
| 3 | 使用 `user:farm:{user_id}:summary` 作为缓存key |

---

## 六、关键设计决策

### 6.1 为什么不用 Milvus 向量化用户业务数据？

| 方案 | 优点 | 缺点 |
|------|------|------|
| **A. 直接查DB + 摘要注入（推荐）** | 实时、准确、实现简单、无额外存储 | 用户数据量大时查询稍慢 |
| B. 业务数据同步到Milvus | 可用向量语义检索 | 数据同步复杂、一致性难保证、需要增量更新 |

**选择方案A**：用户业务数据（农场、轨迹、诊断）是结构化数据，数量有限（通常 <100 条），直接查 DB 并格式化为摘要即可。向量检索适合非结构化知识文档，不适合结构化业务数据。

### 6.2 为什么不用 LLM 做意图识别？

| 方案 | 延迟 | 准确率 | 成本 |
|------|------|--------|------|
| **关键词匹配（推荐）** | <1ms | 85-90% | 免费 |
| LLM意图分类 | 500-2000ms | 95%+ | 每次调用 |

**选择关键词匹配**：意图识别是辅助性的，宁可多注入一点上下文（关键词误匹配），也不能增加明显延迟。Phase 2 可在查询改写阶段让 LLM 顺带输出意图标签（零额外延迟）。

### 6.3 上下文注入量控制

| 模块 | 默认注入量 | 上限 |
|------|-----------|------|
| 农场概况 | 全量（通常 <2KB） | 4KB |
| 轨迹数据 | 最近5条（约1KB） | 8KB |
| 诊断历史 | 最近3条（约1KB） | 4KB |
| 营销历史 | 最近3条（约0.5KB） | 2KB |

总注入量控制在 **10KB 以内**，避免挤占 LLM 上下文窗口。

---

## 七、文件变更清单

| 操作 | 文件路径 | 说明 |
|------|----------|------|
| **新建** | `app/services/user_context.py` | UserContextService 核心服务 |
| **修改** | `app/services/rag_service.py` | 集成 UserContextService，注入上下文 |
| **修改** | `app/prompts/system_prompt.txt` | 增加用户数据引用指引 |
| **修改** | `app/services/rag/retrieval.py` | 可选：调整检索策略，避免与用户数据重复 |
| **修改** | `frontend/app.js` | Phase 4：渲染数据来源卡片 |
| **修改** | `frontend/styles.css` | Phase 4：数据卡片样式 |

---

## 八、风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 用户数据量大导致上下文超长 | LLM截断，回答质量下降 | 严格控制注入量上限，按时间倒序取最近N条 |
| 关键词意图误判 | 注入无关上下文，浪费token | 误判代价低（多注入无害），后续升级为LLM意图标签 |
| 数据库查询增加延迟 | 问答响应变慢 | 农场数据小，查询 <10ms；轨迹用Redis缓存 |
| 用户数据敏感性 | 隐私风险 | 数据按 user_id 严格隔离，不过期不跨用户 |

---

## 九、总结

本方案的核心原则是 **"不迁移数据，只建立索引"**：

1. 各模块数据**原地存储**，不改变现有数据模型
2. 新增 `UserContextService` 作为**聚合层**，按需检索并格式化
3. 在 RAG Chat Pipeline 中**注入结构化摘要**到 LLM 上下文
4. 通过**意图识别**控制注入范围，避免无关数据干扰
5. 分阶段实现，Phase 1（农场数据）即可获得显著体验提升
