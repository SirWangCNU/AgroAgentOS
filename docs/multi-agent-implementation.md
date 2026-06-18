
# AgroAgentOS 多智能体系统实施文档

> 实施日期: 2026-06-13
> 范围: Orchestrator Agent + 种植顾问 Agent + 前端改造

---

## 一、架构总览

### 旧架构（保留不变）

```
用户输入 → SkillRouter → Planner → Executor → Replanner → [END]
                                    ↑               ↓
                                    └── 继续执行 ←──┘
```

- **模式**: 单 Skill 线性执行 (Plan-Execute-Replan)
- **入口**: `POST /api/v1/aiops/diagnose` (mode="legacy")
- **图构建**: `app/agents/graph.py` → `build_aiops_graph()`
- **状态**: `PlanExecuteState`
- **服务**: `app/services/aiops_service.py` → `stream_diagnose()`

### 新架构（新增，与旧架构并存）

```
用户输入 → Orchestrator (意图分类) → [fan-out via Send]
                                          ├──► 种植顾问 Agent ──┐
                                          ├──► 病虫害 Agent ───┤ (未来)
                                          └──► 营销 Agent ─────┘
                                                                │
                                                                ▼
                                                          聚合器 → 最终回复
```

- **模式**: 多 Agent 并发编排 (Orchestrator + Fan-out/Fan-in)
- **入口**: `POST /api/v1/aiops/diagnose` (mode="orchestrator" 或 "auto")
- **图构建**: `app/agents/orchestrator_graph.py` → `build_orchestrator_graph()`
- **状态**: `OrchestratorState`
- **服务**: `app/services/aiops_service.py` → `stream_orchestrate()`

### 模式切换

```json
POST /api/v1/aiops/diagnose
{
  "query": "西红柿怎么施肥",
  "mode": "auto"          // auto | orchestrator | legacy
}
```

| mode | 行为 |
|------|------|
| `auto` | 根据 `settings.orchestrator_enabled` 配置自动选择（默认走 Orchestrator） |
| `orchestrator` | 强制走 Orchestrator 多Agent编排 |
| `legacy` | 强制走旧 Plan-Execute-Replan |

---

## 二、后端变更清单

### 2.1 保留不变的文件（旧流程完全不受影响）

| 文件 | 说明 |
|------|------|
| `app/agents/graph.py` | 旧 Plan-Execute-Replan 图定义，不变 |
| `app/agents/skill_router.py` | 旧 Skill Router 节点，不变 |
| `app/agents/planner.py` | 旧 Planner 节点，不变 |
| `app/agents/executor.py` | 旧 Executor 节点，不变 |
| `app/agents/replanner.py` | 旧 Replanner 节点，不变 |
| `app/agents/fork_runner.py` | 旧 Fork 子图，不变 |
| `app/agents/stream_sink.py` | 流式事件桥接，不变 |
| `app/agents/subagents/` | 旧子 Agent 定义，不变 |
| `app/runtime/agent_harness.py` | Agent 策略中心，不变 |
| `app/runtime/tool_runner.py` | 并行工具执行器，不变 |
| `app/runtime/tool_filter.py` | 工具过滤器，不变 |
| `app/runtime/permissions.py` | 权限系统，不变 |
| `app/runtime/transitions.py` | 状态转换日志，不变 |
| `app/tools/` | 所有工具（天气/知识库/时间），不变 |
| `app/skills/` | 现有 6 个 Skill 定义，不变 |
| `app/services/rag_service.py` | RAG Chat 服务，不变 |
| `app/api/v1/chat.py` | RAG Chat API，不变 |
| `app/core/llm.py` | LLM 工厂，不变 |
| `app/core/structured.py` | 结构化输出，不变 |
| `app/core/vector_store.py` | 向量数据库，不变 |
| `app/core/mcp_client.py` | MCP 客户端，不变 |

### 2.2 新建文件（6 个）

#### `app/agents/state.py` — 新增类型定义

在现有 `PlanExecuteState`、`Act`、`Plan` 之后追加：

```python
class IntentResult(BaseModel):
    """意图分类结果"""
    intent: str          # crop_advisory / pest_diagnosis / weather_calendar / marketing / knowledge_qa / policy
    confidence: float    # 0-1
    reason: str

class BranchResult(TypedDict):
    """单个 Agent 分支的执行结果"""
    agent_name: str      # Agent 显示名
    skill_name: str      # Skill name
    response: str        # 最终回复
    tokens_used: int
    tool_calls: int
    elapsed_ms: int

class OrchestratorState(TypedDict):
    """Orchestrator 主图状态"""
    input: str
    intents: List[IntentResult]
    dispatched_agents: List[str]
    branch_results: Annotated[List[BranchResult], operator.add]  # 累加
    final_response: str
    session_context: str
    iteration: int
    permission_mode: str
    transition_history: Annotated[List[StateTransition], operator.add]
```

#### `app/agents/intent_classifier.py` — 意图分类器

- **职责**: 将用户输入映射到 6 大农业意图类别
- **策略**: 关键词预筛（快）→ LLM 结构化分类（准）
- **关键函数**:
  - `classify_intents(user_input, session_context)` → `IntentClassification`
  - `map_intents_to_agents(intents)` → `List[str]`（Agent 名称列表）
- **关键词预筛**: 复用 `skill_router.py` 的 `_AGRICULTURE_KEYWORDS` 和 `_OUT_OF_SCOPE_KEYWORDS`
- **LLM 模型**: `harness.router_model()`（默认 qwen-turbo，快且便宜）
- **结构化输出 Schema**: `IntentClassification(is_agriculture, intents, reason)`
- **兜底**: LLM 失败时默认走 `crop_advisory`

#### `app/agents/aggregator.py` — 结果聚合器

- **职责**: 将多个 Agent 的结果合并为连贯回复
- **策略**:
  - 单 Agent → 直接返回其 response
  - 多 Agent → LLM 聚合（去重、合并、结构化）
  - LLM 失败 → 简单拼接兜底
- **关键函数**: `aggregate_results(user_input, results)` → `str`
- **LLM 模型**: `harness.report_model()`（默认 qwen-max，质量优先）

#### `app/agents/orchestrator.py` — 主编排器

- **职责**: 意图分类 → Agent 派发 → 结果聚合
- **三个节点函数**:
  1. `orchestrator_classify_node(state)` — 意图分类，决定需要哪些 Agent
  2. `dispatch_to_agents(state)` — Fan-out，返回 `List[Send]` 实现并发派发
  3. `orchestrator_aggregate_node(state)` — Fan-in，聚合多路结果
- **非农业处理**: 直接返回拒绝回复，不派发 Agent
- **并发限制**: 最多 3 个 Agent 并发

#### `app/agents/orchestrator_graph.py` — Orchestrator Graph

- **职责**: 定义 Orchestrator 多Agent编排图
- **图结构**:
  ```
  [START] → orchestrator_classify → [Send fan-out]
                                        ├──► crop_advisory ──┐
                                        └──► (future agents) ┘
                                                              │
                                                              ▼
                                                          aggregator → [END]
  ```
- **关键函数**: `build_orchestrator_graph()` → `CompiledStateGraph`
- **LangGraph 特性**: 使用 `Send()` API 实现真正的并发 fan-out

#### `app/agents/crop_advisory.py` — 种植顾问 Agent

- **职责**: 封装种植顾问为独立 Agent 节点
- **内部逻辑**: 复用现有 `build_aiops_graph()` 跑完整 Plan-Execute-Replan
- **初始状态**: 强制 `selected_skill="crop_advisory"`
- **关键函数**: `crop_advisory_node(state)` → `{"branch_results": [BranchResult]}`
- **事件推送**: 通过 `stream_sink.emit()` 推送 `agent_start` / `agent_complete` 事件

#### `app/skills/definitions/crop_advisory/SKILL.md` — 种植顾问 Skill

```yaml
name: crop_advisory
display_name: 种植顾问
description: 根据作物种类、生长阶段、气候条件给出施肥、灌溉、播种、田间管理建议
triggers: [施肥, 灌溉, 播种, 种植, 生长阶段, 浇水, 追肥, 底肥, 育苗, 插秧, ...]
allowed_tools: [search_knowledge_base, get_weather, get_current_time]
risk_level: low
context: inline
```

### 2.3 改造文件（4 个）

#### `app/config.py` — 新增配置项

```python
# Orchestrator 多Agent编排
orchestrator_enabled: bool = True          # 是否启用 Orchestrator 模式
orchestrator_max_agents: int = 3           # 单次最多并发 Agent 数
orchestrator_timeout_sec: int = 120        # 总超时
orchestrator_model: str = ""               # 意图分类用的模型 (留空走 router_model)
```

#### `app/schemas/aiops.py` — 请求和事件类型扩展

`DiagnosisRequest` 新增字段:
```python
mode: Literal["auto", "orchestrator", "legacy"] = "auto"
```

`EventType` 新增:
```python
"agent_start"     # Agent 分支启动
"agent_complete"  # Agent 分支完成
"transition"      # 状态转换记录
```

#### `app/services/aiops_service.py` — 新增 Orchestrator 服务

新增函数:
- `_get_orchestrator_graph()` — Orchestrator Graph 单例
- `stream_orchestrate(query, session_id)` — Orchestrator 模式流式诊断
- `_convert_orchestrator_node_event(node_name, node_output)` — 节点事件转 SSE

新增 SSE 事件类型:

| type | stage | 说明 |
|------|-------|------|
| `transition` | `classify_ok` | 意图分类完成 |
| `transition` | `out_of_scope` | 非农业输入 |
| `skill_selected` | `intents_classified` | 意图分类结果 |
| `agent_start` | `agent_start` | Agent 分支启动 |
| `agent_complete` | `agent_done` | Agent 分支完成 |
| `transition` | `aggregate_ok` | 聚合完成 |
| `report` | `orchestration_complete` | 最终报告 |
| `report` | `orchestrator_reject` | 非农业拒绝 |

#### `app/api/v1/aiops.py` — API 入口改造

- `aiops_diagnose()` 根据 `req.mode` 选择 `stream_orchestrate` 或 `stream_diagnose`
- 更新 OpenAPI 文档描述

---

## 三、前端变更清单

### 3.1 保留不变的部分

| 文件/组件 | 说明 |
|-----------|------|
| `components/chat/MessageBubble.tsx` | 消息气泡，不变 |
| `components/chat/WelcomeScreen.tsx` | 欢迎页，不变 |
| `components/chat/ConversationSidebar.tsx` | 侧边栏，不变 |
| `components/chat/ProgressSteps.tsx` | RAG 模式进度条，不变 |
| `stores/auth.ts` | 认证 store，不变 |
| `stores/ui.ts` | UI store，不变 |
| `stores/health.ts` | 健康 store，不变 |
| `api/client.ts` | API 客户端，不变 |
| `api/chat.ts` | RAG Chat API，不变 |
| `api/sessions.ts` | 会话 API，不变 |
| `pages/Login.tsx` | 登录页，不变 |
| `pages/Dashboard.tsx` | 仪表盘，不变 |
| `pages/Weather.tsx` | 天气页，不变 |
| `pages/Farms.tsx` | 农场页，不变 |
| `pages/Knowledge.tsx` | 知识库页，不变 |
| `pages/Marketing.tsx` | 营销页，不变 |
| `pages/PestDiagnosis.tsx` | 病虫害页，不变 |
| `pages/Users.tsx` | 用户管理页，不变 |
| `App.tsx` | 路由配置，不变 |

### 3.2 新建文件（3 个）

#### `api/aiops.ts` — AIOps API 客户端

```typescript
export async function aiopsStream(
  query: string,
  mode: "auto" | "orchestrator" | "legacy" = "auto",
  sessionId: string = "default"
): Promise<Response>
```

调用 `POST /api/v1/aiops/diagnose`，返回原始 Response 供 SSE 消费。

#### `components/chat/IntentBadge.tsx` — 意图标签组件

展示 Orchestrator 意图分类结果：

```
意图识别: [🌱 种植建议 95%] [🐛 病虫害 75%]
```

| 意图 | 图标 | 颜色 |
|------|------|------|
| crop_advisory | 🌱 | green |
| pest_diagnosis | 🐛 | red |
| weather_calendar | 🌤️ | blue |
| marketing | 📝 | purple |
| knowledge_qa | 📚 | amber |
| policy | 📋 | gray |

#### `components/chat/AgentProgress.tsx` — Agent 进度卡片组件

展示多 Agent 并发执行状态：

```
⚡ 正在并行执行 2 个 Agent (1/2 完成)

┌──────────────┐ ┌──────────────┐
│ 🌱 种植顾问   │ │ 🐛 病虫害诊断 │
│ ✅ 完成 2.1s  │ │ ⏳ 分析中...  │
│ • 检索知识库  │ │ • 检索知识库  │
│ • 获取天气    │ │              │
└──────────────┘ └──────────────┘
```

状态流转: `pending → running → done/error`

### 3.3 改造文件（3 个）

#### `types/chat.ts` — 新增接口

```typescript
interface IntentResult {
  intent: string;
  confidence: number;
  reason: string;
}

interface AgentProgress {
  id: string;
  name: string;
  icon: string;
  status: "pending" | "running" | "done" | "error";
  steps: string[];
  elapsed_ms?: number;
  result_preview?: string;
}

interface OrchestratorState {
  phase: "classify" | "dispatch" | "running" | "aggregate" | "done";
  intents: IntentResult[];
  agents: AgentProgress[];
  final_response?: string;
}
```

#### `stores/conversation.ts` — 新增状态和 Actions

新增状态字段:
```typescript
orchestratorPhase: "idle" | "classify" | "dispatch" | "running" | "aggregate" | "done";
liveIntents: IntentResult[];
agentProgress: AgentProgress[];
orchestratorMode: boolean;
```

新增 Actions:
```typescript
setOrchestratorMode(v: boolean): void;
setOrchestratorPhase(phase): void;
setLiveIntents(intents: IntentResult[]): void;
initAgentProgress(agents: AgentProgress[]): void;
updateAgentProgress(id: string, update: Partial<AgentProgress>): void;
clearOrchestratorState(): void;
```

#### `components/chat/ChatInput.tsx` — 新增模式切换

底部新增模式切换按钮:

```
[🌱 农业助手] [🔧 智能诊断]          [🌐联网] [🔧MCP]
```

- "农业助手" → 走 `/chat/stream`（RAG 模式，原有功能）
- "智能诊断" → 走 `/aiops/diagnose`（Orchestrator 模式）

新增 Props:
```typescript
chatMode?: "rag" | "orchestrator";
onChatModeChange?: (v: "rag" | "orchestrator") => void;
```

#### `pages/Chat.tsx` — SSE 事件处理改造

**核心改动**: `handleSend()` 拆分为两个函数：

```typescript
const handleSend = async (text, image) => {
  // ... 通用逻辑 ...
  if (chatMode === "orchestrator") {
    await handleOrchestratorSend(question, convId);  // 新增
  } else {
    await handleRagSend(question, convId);            // 原有逻辑
  }
};
```

`handleRagSend()` — 原有 RAG 流程，逻辑不变

`handleOrchestratorSend()` — 新增 Orchestrator 流程：
- 处理 `transition` 事件 → 更新意图分类状态
- 处理 `agent_start` 事件 → 更新 Agent 进度为 running
- 处理 `agent_complete` 事件 → 更新 Agent 进度为 done
- 处理 `step_complete` 事件 → 更新 Agent 步骤列表
- 处理 `report` 事件 → 设置最终回复
- 处理 `complete` 事件 → 标记完成

**渲染改造**: 流式展示区域根据 `chatMode` 切换：

```tsx
{chatMode === "orchestrator" && orchestratorPhase !== "idle" ? (
  <>
    <IntentBadge intents={liveIntents} />
    <AgentProgressPanel phase={orchestratorPhase} agents={agentProgress} />
  </>
) : (
  <ProgressSteps steps={liveProgress} />  // 原有 RAG 进度条
)}
```

---

## 四、数据流对比

### 旧流程 (RAG 模式)

```
用户输入
  → POST /api/v1/chat/stream
  → rag_service.stream_chat()
  → Redis 会话记忆加载
  → 查询改写 (LLM)
  → Milvus 向量检索
  → 可选: 联网搜索
  → LLM 生成回答
  → SSE: progress → token → citations → end
```

### 旧流程 (AIOps Legacy 模式)

```
用户输入
  → POST /api/v1/aiops/diagnose (mode=legacy)
  → stream_diagnose()
  → SkillRouter → Planner → Executor → Replanner (循环)
  → SSE: start → skill_selected → plan → step_complete → report → complete
```

### 新流程 (Orchestrator 模式)

```
用户输入
  → POST /api/v1/aiops/diagnose (mode=orchestrator)
  → stream_orchestrate()
  → orchestrator_classify (意图分类)
  → [Send fan-out] → crop_advisory Agent (并发)
                       └── 内部: SkillRouter → Planner → Executor → Replanner
  → [fan-in] → aggregator (结果聚合)
  → SSE: start → transition(classify_ok) → skill_selected → agent_start
       → step_start → tool_call → ... → agent_complete → report → complete
```

---

## 五、配置项汇总

### 新增配置 (`.env`)

```env
# Orchestrator 多Agent编排
ORCHESTRATOR_ENABLED=true
ORCHESTRATOR_MAX_AGENTS=3
ORCHESTRATOR_TIMEOUT_SEC=120
ORCHESTRATOR_MODEL=              # 留空走 DASHSCOPE_ROUTER_MODEL
```

### 保留配置（不变）

所有现有配置项保持不变，包括：
- DashScope/DeepSeek LLM 配置
- Milvus 向量数据库配置
- RAG 配置
- MCP 服务器配置
- Agent 相关配置 (agent_max_steps, agent_max_reroutes 等)
- 权限配置
- 日志配置

---

## 六、测试验证结果

| 测试项 | 结果 | 说明 |
|--------|------|------|
| TypeScript 编译 | ✅ 通过 | `npx tsc --noEmit` 无错误 |
| Vite 生产构建 | ✅ 通过 | 705KB, 6.75s |
| 后端模块导入 | ✅ 通过 | 所有新模块正常导入 |
| Orchestrator Graph 编译 | ✅ 通过 | CompiledStateGraph |
| crop_advisory Skill 注册 | ✅ 通过 | 7 个 Skill 全部加载 |
| 旧 Graph 后向兼容 | ✅ 通过 | build_aiops_graph() 正常 |
| 单意图端到端 | ✅ 通过 | "西红柿怎么施肥" → 意图分类(crop_advisory) → Agent执行 → 聚合 → 报告(866字) |
| 非农业拒绝 | ✅ 通过 | "今天股市怎么样" → 直接拒绝回复 |
| Orchestrator SSE 事件 | ✅ 通过 | 76 个事件，包含完整生命周期 |

### 端到端事件流 (单意图)

```
[1]  type=start,           stage=orchestration_init
[2]  type=transition,      stage=classify_ok           ← 意图分类完成
[3]  type=skill_selected,  stage=intents_classified    ← 意图: crop_advisory
[4]  type=agent_start,     stage=agent_start           ← 种植顾问启动
[5]  type=step_start,      stage=step_start            ← Plan-Execute 第1步
[6]  type=tool_call,       stage=tool_call             ← 搜索知识库
[7]  type=tool_call,       stage=tool_call             ← 获取天气
[8]  type=step_start,      stage=step_start            ← Plan-Execute 第2步
[9]  type=tool_call,       stage=tool_call             ← 搜索知识库
[10] type=agent_complete,  stage=agent_complete         ← 种植顾问完成
[11] type=step_complete,   stage=agent_done            ← Agent 结果
[12] type=transition,      stage=aggregate_ok          ← 聚合完成
[13] type=report,          stage=orchestration_complete ← 最终报告(866字)
```

---

## 七、后续扩展指南

### 新增 Agent（如病虫害诊断）

只需 3 步：

1. **新建 Agent 节点** `app/agents/pest_diagnosis.py`
   ```python
   async def pest_diagnosis_node(state: dict) -> dict:
       # 参照 crop_advisory.py 实现
       graph = build_aiops_graph()
       initial_state = {"input": state["input"], "selected_skill": "pest_diagnosis", ...}
       # 跑完整 Plan-Execute-Replan
       return {"branch_results": [BranchResult(...)]}
   ```

2. **在 orchestrator_graph.py 注册节点**
   ```python
   workflow.add_node("pest_diagnosis", pest_diagnosis_node)
   workflow.add_edge("pest_diagnosis", "aggregator")
   ```

3. **在前端 AgentProgress.tsx 添加图标映射**
   ```typescript
   pest_diagnosis: { name: "病虫害诊断", icon: "🐛" }
   ```

### 新增意图类别

在 `intent_classifier.py` 的 `INTENT_AGENT_MAP` 和 `_SYSTEM_PROMPT` 中添加新意图即可。

### 调整并发数

修改 `.env` 中的 `ORCHESTRATOR_MAX_AGENTS`（默认 3）。
