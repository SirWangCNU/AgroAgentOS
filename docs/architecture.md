# AgroAgentOS 系统架构文档

> 版本：1.0 | 最后更新：2026-06-13

---

## 目录

- [1. 项目概览](#1-项目概览)
- [2. 整体架构](#2-整体架构)
- [3. 目录结构](#3-目录结构)
- [4. 后端技术栈](#4-后端技术栈)
  - [4.1 核心框架](#41-核心框架)
  - [4.2 LLM 与 Agent 依赖](#42-llm-与-agent-依赖)
  - [4.3 数据存储](#43-数据存储)
  - [4.4 工具链与辅助库](#44-工具链与辅助库)
  - [4.5 配置管理](#45-配置管理)
- [5. 前端技术栈](#5-前端技术栈)
  - [5.1 核心框架](#51-核心框架)
  - [5.2 状态管理](#52-状态管理)
  - [5.3 路由与页面](#53-路由与页面)
  - [5.4 API 通信层](#54-api-通信层)
  - [5.5 UI 组件与样式](#55-ui-组件与样式)
- [6. API 路由总览](#6-api-路由总览)
- [7. 数据库模型](#7-数据库模型)
  - [7.1 关系型数据库模型](#71-关系型数据库模型)
  - [7.2 向量数据库（Milvus）](#72-向量数据库milvus)
- [8. RAG 检索增强生成管线](#8-rag-检索增强生成管线)
- [9. Agent 系统架构](#9-agent-系统架构)
  - [9.1 LangGraph 核心状态图](#91-langgraph-核心状态图)
  - [9.2 五大 Agent 节点详解](#92-五大-agent-节点详解)
  - [9.3 Agent 状态定义](#93-agent-状态定义)
  - [9.4 Agent Harness（运行时管理器）](#94-agent-harness运行时管理器)
- [10. 多 Agent 编排模式](#10-多-agent-编排模式)
  - [10.1 Skill-first 路由模式](#10.1-skill-first-路由模式)
  - [10.2 Plan-Execute-Replan 循环](#102-plan-execute-replan-循环)
  - [10.3 Skill 协作（多技能联动）](#103-skill-协作多技能联动)
  - [10.4 Skill Reroute（技能重路由）](#104-skill-reroute技能重路由)
  - [10.5 Fork 模式（子图隔离）](#105-fork-模式子图隔离)
  - [10.6 Subagent 委托](#106-subagent-委托)
  - [10.7 并行工具执行](#107-并行工具执行)
- [11. Skill 技能系统](#11-skill-技能系统)
- [12. MCP 工具服务器](#12-mcp-工具服务器)
- [13. 知识库系统](#13-知识库系统)
- [14. 服务端口与部署架构](#14-服务端口与部署架构)
- [15. 部署方案](#15-部署方案)

---

## 1. 项目概览

**AgroAgentOS** 是一个面向农业领域的智能 Agent 操作系统，基于 **LangGraph + FastAPI + React** 构建。系统通过多 Agent 编排实现农业问答、病虫害诊断、天气咨询、营销内容生成等业务能力，支持 RAG（检索增强生成）知识库检索、YOLO 图像识别、MCP 工具调用等能力。

### 核心特性

- **多 Agent 编排**：基于 LangGraph 的 Plan-Execute-Replan 循环，支持技能路由、多技能协作、技能重路由、子图 Fork 等模式
- **RAG 知识检索**：Milvus 向量数据库 + BM25 稀疏检索 + Reranker 重排序的混合检索管线
- **Skill 技能系统**：声明式 YAML+Markdown 技能定义，支持热加载和动态路由
- **MCP 工具协议**：Model Context Protocol 工具服务器，支持天气查询、网络搜索等外部工具
- **YOLO 图像识别**：基于 ONNX Runtime 的病虫害图像识别
- **SSE 流式输出**：全链路 Server-Sent Events 流式响应，支持实时进度追踪

---

## 2. 整体架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Frontend (React + Vite)                      │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │
│  │ Chat UI  │ │ Weather  │ │  Pest    │ │  Farms   │ │Marketing │  │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘  │
│       └─────────────┴────────────┴────────────┴────────────┘        │
│                           │ SSE / REST API                          │
└───────────────────────────┼─────────────────────────────────────────┘
                            │
┌───────────────────────────┼─────────────────────────────────────────┐
│                    FastAPI Backend (Port 9800)                       │
│  ┌────────────────────────┼──────────────────────────────────────┐  │
│  │              API Routers (/api/v1/)                           │  │
│  │  /chat/stream  /aiops/diagnose  /skills  /documents  ...     │  │
│  └────────────────────────┼──────────────────────────────────────┘  │
│                           │                                         │
│  ┌────────────────────────┼──────────────────────────────────────┐  │
│  │              LangGraph Agent Engine                           │  │
│  │  ┌───────────┐  ┌──────────┐  ┌───────────┐  ┌───────────┐  │  │
│  │  │SkillRouter│─▶│ Planner  │─▶│ Executor  │─▶│Replanner  │  │  │
│  │  └───────────┘  └──────────┘  └───────────┘  └───────────┘  │  │
│  │       │                                           │          │  │
│  │       ▼                                           ▼          │  │
│  │  ┌───────────┐                              ┌───────────┐    │  │
│  │  │ForkSkill  │                              │ Subagents │    │  │
│  │  └───────────┘                              └───────────┘    │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                           │                                         │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────────┐   │
│  │  Skills   │  │   Tools   │  │AgentHarness│  │ToolRunner     │   │
│  │ Registry  │  │  (MCP等)  │  │(Prompt/Model)│ │(并行工具执行)│   │
│  └───────────┘  └───────────┘  └───────────┘  └───────────────┘   │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                    RAG Pipeline                               │  │
│  │  Embedding(text-embedding-v4) → Milvus + BM25 → Reranker    │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐       │
│  │  SQLite/  │  │  Milvus   │  │   Redis   │  │  MCP      │       │
│  │  MySQL    │  │  (向量DB) │  │  (会话)   │  │  Servers  │       │
│  └───────────┘  └───────────┘  └───────────┘  └───────────┘       │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 3. 目录结构

```
AgroAgentOS/
├── app/                          # FastAPI 后端应用
│   ├── main.py                   # 应用入口，lifespan 生命周期管理
│   ├── config.py                 # pydantic-settings 配置管理（单例）
│   ├── agents/                   # Agent 编排核心
│   │   ├── graph.py              # LangGraph 状态图构建
│   │   ├── state.py              # Agent 状态定义（TypedDict）
│   │   ├── skill_router.py       # 技能路由 Agent
│   │   ├── planner.py            # 计划生成 Agent
│   │   ├── executor.py           # 计划执行 Agent
│   │   ├── replanner.py          # 重规划 Agent
│   │   ├── fork_runner.py        # Fork 子图运行器
│   │   └── subagents/            # 子 Agent 委托
│   │       └── runner.py         # Subagent ReAct 执行器
│   ├── core/                     # 核心基础设施
│   │   ├── database.py           # 数据库连接管理器
│   │   ├── sqlite.py             # SQLAlchemy ORM 基类 + 模型
│   │   ├── vector_store.py       # Milvus 向量存储 + RAG 管线
│   │   ├── redis_client.py       # Redis 客户端
│   │   └── mcp_loader.py         # MCP 工具加载器
│   ├── runtime/                  # 运行时管理
│   │   ├── agent_harness.py      # Agent 中央配置与 Prompt 管理
│   │   └── tool_runner.py        # 并行工具执行引擎
│   ├── skills/                   # 技能系统
│   │   ├── registry.py           # 技能注册表（单例）
│   │   └── definitions/          # 技能定义文件
│   │       ├── agriculture_qa/
│   │       ├── weather_advice/
│   │       ├── pest_diagnosis/
│   │       ├── marketing_generator/
│   │       ├── knowledge_retrieval/
│   │       ├── generic_oncall/
│   │       └── crop_advisory/
│   ├── tools/                    # 内置工具
│   │   ├── weather.py            # 天气查询工具
│   │   ├── web_search.py         # 网络搜索工具
│   │   ├── knowledge.py          # 知识库检索工具
│   │   ├── rag_tool.py           # RAG 工具
│   │   └── oncall.py             # 运维工具
│   ├── services/                 # 业务服务层
│   │   ├── chat_service.py       # 聊天服务
│   │   ├── image_analysis.py     # YOLO 图像识别
│   │   └── ...
│   ├── models/                   # 数据模型
│   ├── schemas/                  # Pydantic 请求/响应 Schema
│   └── routers/                  # API 路由
│       ├── chat.py               # 聊天 SSE 流式路由
│       ├── aiops.py              # Agent 诊断路由
│       ├── skills.py             # 技能列表路由
│       ├── auth.py               # JWT 认证路由
│       ├── farms.py              # 农场管理路由
│       └── ...
├── frontend-react/               # React 前端 SPA
│   ├── src/
│   │   ├── App.tsx               # 路由定义
│   │   ├── stores/               # Zustand 状态管理
│   │   │   ├── conversation.ts   # 对话状态（流式、引用、进度）
│   │   │   ├── auth.ts           # 认证状态
│   │   │   ├── ui.ts             # UI 状态
│   │   │   └── health.ts         # 健康检查状态
│   │   ├── api/                  # API 客户端
│   │   │   └── client.ts         # authFetch + consumeSSE
│   │   ├── components/           # 通用组件
│   │   ├── pages/                # 页面组件
│   │   └── layouts/              # 布局组件
│   ├── package.json
│   └── vite.config.ts
├── knowledge_base/               # 农业知识文档（Markdown）
│   ├── planting/                 # 种植类
│   ├── pest_control/             # 病虫害防治类
│   ├── soil/                     # 土壤类
│   └── weather/                  # 天气类
├── mcp_servers/                  # MCP 工具服务器
│   ├── docker_server.py
│   ├── network_server.py
│   ├── system_server.py
│   ├── websearch_server.py
│   └── winlog_server.py
├── models/                       # YOLO ONNX 模型文件
├── scripts/                      # 知识库导入脚本
├── alembic/                      # 数据库迁移
├── data/                         # 运行时数据
├── docker-compose.yml            # 基础设施服务编排
├── requirements.txt              # Python 依赖
├── .env.example                  # 环境变量模板
├── deploy.sh                     # Linux 一键部署脚本
├── run.ps1                       # Windows PowerShell 启动脚本
└── manage.sh                     # 管理脚本
```

---

## 4. 后端技术栈

### 4.1 核心框架

| 组件 | 技术 | 版本 | 用途 |
|------|------|------|------|
| Web 框架 | FastAPI | 0.115+ | 异步 HTTP API 服务 |
| ASGI 服务器 | Uvicorn | - | 生产级 ASGI 服务器 |
| SSE 支持 | sse-starlette | - | Server-Sent Events 流式响应 |
| 文件上传 | python-multipart + aiofiles | - | 文件上传与异步文件操作 |
| 配置管理 | pydantic-settings | - | 基于 `.env` 的类型安全配置 |
| 日志 | loguru | - | 结构化日志 |

**入口文件**：`app/main.py`

应用使用 FastAPI 的 `lifespan` 上下文管理器进行生命周期管理：

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    validate_config()          # 验证配置
    connect_milvus()           # 连接向量数据库
    connect_database()         # 连接关系型数据库（SQLite/MySQL）
    connect_redis()            # 连接 Redis
    ensure_admin_user()        # 确保管理员用户存在
    load_mcp_tools()           # 加载 MCP 工具
    yield
    # Shutdown
    disconnect_all()           # 断开所有服务连接
```

应用注册了 **15 个 API 路由器**，同时作为 React SPA 的静态文件服务器。

### 4.2 LLM 与 Agent 依赖

| 组件 | 技术 | 版本 | 用途 |
|------|------|------|------|
| LLM 编排框架 | LangChain | 1.x | LLM 调用抽象层 |
| Agent 编排引擎 | LangGraph | 1.x | 基于图的 Agent 编排 |
| 检查点存储 | langgraph-checkpoint | 3.x | Agent 状态持久化 |
| LLM 接口 | langchain-openai | 1.x | 兼容 DashScope/DeepSeek 的 OpenAI 协议 |
| MCP 适配 | langchain-mcp-adapters | 0.2.x | MCP 工具与 LangChain 集成 |
| MCP 服务端 | fastmcp | 2.14+ | MCP 工具服务器框架 |

**LLM 模型配置**：

| 用途 | 模型 | 提供商 |
|------|------|--------|
| 技能路由 | qwen-turbo | DashScope |
| 计划生成 | 可配置（默认 qwen-turbo） | DashScope |
| 计划执行 | 可配置（默认 qwen-max） | DashScope |
| 报告生成 | 可配置（report_model） | DashScope |
| RAG 聊天 | 可配置 | DashScope/DeepSeek |
| 文本嵌入 | text-embedding-v4 | DashScope |
| 重排序 | gte-rerank-v2 | DashScope |

### 4.3 数据存储

| 组件 | 技术 | 版本 | 用途 |
|------|------|------|------|
| 关系型数据库 | SQLite / MySQL | - | 业务数据持久化（通过 `USE_SQLITE` 切换） |
| 向量数据库 | Milvus | 2.4.10 | 知识库向量检索 |
| 对象存储 | MinIO | 2023-03-20 | Milvus 底层存储 |
| 缓存/会话 | Redis | 7-alpine | 会话记忆、可选缓存 |
| 数据库迁移 | Alembic | - | 数据库 Schema 版本管理 |

**数据库双模式**：

- **开发环境（默认）**：SQLite，数据文件 `data/agro_agent.db`，零配置
- **生产环境**：MySQL，通过 pymysql 连接池，支持连接池配置

管理类：`app/core/database.py` → `DatabaseManager`

### 4.4 工具链与辅助库

| 类别 | 库 | 用途 |
|------|-----|------|
| HTTP 客户端 | httpx | 异步 HTTP 请求 |
| 稀疏检索 | rank_bm25 | BM25 算法实现 |
| 矩阵计算 | numpy | 向量相似度计算 |
| 进程监控 | psutil | 系统资源监控 |
| Token 计数 | tiktoken | Token 用量统计 |
| Redis 客户端 | redis | 会话缓存 |
| 图表生成 | matplotlib | 数据可视化 |
| 图像推理 | onnxruntime + Pillow | YOLO 病虫害识别 |
| 密码加密 | bcrypt | 用户密码哈希 |
| JWT | python-jose | JWT Token 签发与验证 |

### 4.5 配置管理

配置系统基于 `pydantic-settings`，通过 `app/config.py` 的 `Settings` 类管理，使用 `@lru_cache` 实现单例。

```python
# app/config.py
class Settings(BaseSettings):
    # 应用基础
    APP_NAME: str = "AgroAgentOS"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    HOST: str = "0.0.0.0"
    PORT: int = 9800

    # LLM 配置
    DASHSCOPE_API_KEY: str = ""
    DASHSCOPE_BASE_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    LLM_MODEL: str = "qwen-max"
    LLM_ROUTER_MODEL: str = "qwen-turbo"

    # Milvus 向量数据库
    MILVUS_HOST: str = "localhost"
    MILVUS_PORT: int = 19530
    MILVUS_COLLECTION: str = "agro_agent_kb"

    # RAG 配置
    RAG_TOP_K: int = 10
    RAG_CHUNK_SIZE: int = 512
    RAG_HYBRID_SEARCH: bool = True
    RAG_RERANKER_ENABLED: bool = True

    # Agent 运行时
    MAX_AGENT_STEPS: int = 10
    AGENT_CONCURRENCY: int = 6
    PARALLEL_EXECUTION: bool = True

    # 数据库
    USE_SQLITE: bool = True

    # JWT 认证
    JWT_SECRET_KEY: str = ""
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 1440

    # ... 更多配置项

    class Config:
        env_file = ".env"
```

所有配置通过 `.env` 文件注入，`.env.example` 提供完整模板。

---

## 5. 前端技术栈

### 5.1 核心框架

| 组件 | 技术 | 版本 | 用途 |
|------|------|------|------|
| UI 框架 | React | 19.2.6 | 组件化 UI 开发 |
| 类型系统 | TypeScript | 6.0 | 静态类型检查 |
| 构建工具 | Vite | 8.0 | 快速开发与构建 |
| 包管理 | npm | - | 依赖管理 |

### 5.2 状态管理

使用 **Zustand 5.0** 进行轻量级状态管理，共 4 个 Store：

#### conversation.ts — 对话状态

```typescript
interface ConversationStore {
  // 对话列表
  conversations: Conversation[]
  activeConversationId: string | null

  // 流式状态
  isStreaming: boolean
  streamingContent: string
  progressSteps: ProgressStep[]      // Agent 执行进度
  liveCitations: Citation[]          // 实时引用来源

  // 操作
  sendMessage: (content: string) => Promise<void>
  createConversation: () => Promise<void>
  loadConversations: () => Promise<void>
  // ...
}
```

#### auth.ts — 认证状态

```typescript
interface AuthStore {
  token: string | null
  user: User | null
  login: (username: string, password: string) => Promise<void>
  logout: () => void
  // 持久化到 localStorage
}
```

#### ui.ts — UI 状态

```typescript
interface UIStore {
  sidebarCollapsed: boolean
  searchModalOpen: boolean
  toasts: Toast[]
  // ...
}
```

#### health.ts — 健康检查

```typescript
interface HealthStore {
  healthData: HealthResponse | null
  skills: Skill[]
  // 每 15 秒轮询
}
```

### 5.3 路由与页面

使用 **react-router-dom 7.16** 进行客户端路由：

| 路径 | 页面 | 描述 |
|------|------|------|
| `/login` | LoginPage | 登录页 |
| `/` , `/chat` | ChatPage | 主聊天界面（RAG 问答） |
| `/chat/:sessionId` | ChatPage | 指定会话聊天 |
| `/workspace` | Dashboard | 工作台仪表盘 |
| `/workspace/weather` | WeatherPage | 天气咨询服务 |
| `/workspace/farms` | FarmsPage | 农场管理（含地图） |
| `/workspace/knowledge` | KnowledgePage | 知识库管理 |
| `/workspace/marketing` | MarketingPage | 营销内容生成 |
| `/workspace/pest` | PestPage | 病虫害诊断 |
| `/workspace/users` | UsersPage | 用户管理（仅管理员） |

**布局组件**：

- `AppLayout`：顶层布局，包含 TopBar、可折叠侧边栏（overlay 模式）、Toast 容器
- `WorkspaceLayout`：工作台布局，左侧导航栏 + 内容区

### 5.4 API 通信层

`frontend-react/src/api/client.ts` 提供三个核心函数：

```typescript
// JSON 请求（自动附加 JWT Bearer Token）
async function authFetch<T>(url: string, options?: RequestInit): Promise<T>

// 原始 Response 请求
async function authFetchRaw(url: string, options?: RequestInit): Promise<Response>

// SSE 流式消费（AsyncGenerator）
async function* consumeSSE(url: string, options?: RequestInit): AsyncGenerator<SSEEvent>
```

**SSE 事件类型**：

| 事件 | 描述 |
|------|------|
| `progress` | Agent 执行进度更新 |
| `content` | 流式文本内容 |
| `citation` | 引用来源 |
| `done` | 流结束 |
| `error` | 错误信息 |

### 5.5 UI 组件与样式

| 组件 | 技术 | 用途 |
|------|------|------|
| CSS 框架 | TailwindCSS 4.3 | 原子化 CSS |
| 图标 | Lucide React | SVG 图标库 |
| 地图 | Leaflet + react-leaflet | 农田地图可视化 |
| Markdown | react-markdown + remark-gfm | Markdown 渲染 |
| 数据获取 | @tanstack/react-query 5.100 | 服务端状态管理 |

---

## 6. API 路由总览

所有 API 路由注册在 `/api/v1/` 前缀下：

| 路由前缀 | 方法 | 描述 | 认证 |
|----------|------|------|------|
| `/chat/stream` | POST | RAG 聊天流式接口（SSE） | ✅ |
| `/aiops/diagnose` | POST | 多 Agent 诊断（SSE） | ✅ |
| `/skills` | GET | 列出所有农业技能 | ❌ |
| `/documents` | GET/POST | 知识库文档管理 | ✅ |
| `/documents/upload` | POST | 文档上传 | ✅ |
| `/health` | GET | 健康检查 | ❌ |
| `/health/ready` | GET | 就绪探针 | ❌ |
| `/history` | GET | 查询历史记录 | ✅ |
| `/observability` | GET | Agent 可观测性数据 | ✅ |
| `/diagnosis` | GET | 诊断记录 | ✅ |
| `/weather` | GET | 天气查询 | ✅ |
| `/auth` | POST/GET | JWT 认证（登录、用户管理） | 部分 |
| `/farms` | GET/POST/PUT/DELETE | 农场位置、地块与天气风险管理 | ✅ |
| `/image` | POST | YOLO 病虫害图像识别 | ✅ |
| `/sessions` | GET/POST/DELETE | 聊天会话 CRUD | ✅ |
| `/webhook` | POST | Webhook 端点 | ❌ |

---

## 7. 数据库模型

### 7.1 关系型数据库模型

使用 SQLAlchemy ORM 定义，基础类在 `app/core/sqlite.py`。

#### 用户与认证

| 模型 | 表名 | 字段 |
|------|------|------|
| `User` | `users` | id, username, email, hashed_password, role(admin/user), is_active, created_at |

#### 聊天系统

| 模型 | 表名 | 字段 |
|------|------|------|
| `ChatSession` | `chat_sessions` | id, session_id(UUID), user_id, title, created_at, updated_at |
| `ChatMessage` | `chat_messages` | id, session_id(FK), role(user/assistant/system), content, extra_json(JSON), created_at |

#### Agent 执行日志

| 模型 | 表名 | 字段 |
|------|------|------|
| `AgentRun` | `agent_runs` | id, run_id(UUID), query, skill, status, tokens_used, transitions(JSON), created_at |
| `AgentExecutionLog` | `agent_execution_logs` | id, run_id(FK), step_index, step_name, tool_name, input, result, duration_ms, created_at |

#### 业务记录

| 模型 | 表名 | 字段 |
|------|------|------|
| `HistoryRecord` | `history_records` | id, source(chat/aiops/weather/...), user_id, query, response, metadata_json, created_at |
| `BusinessRecord` | `business_records` | id, key, value(JSON), created_at |
| `WeatherQuery` | `weather_queries` | id, user_id, location, weather_data(JSON), advice, created_at |
| `MarketingTask` | `marketing_tasks` | id, user_id, topic, content, status, created_at |
| `PestDiagnosis` | `pest_diagnoses` | id, user_id, image_path, diagnosis_result(JSON), created_at |

#### 农场管理

| 模型 | 表名 | 字段 |
|------|------|------|
| `Farm` | `farms` | id, name, location, latitude, longitude, area_mu, user_id, created_at |
| `Field` | `fields` | id, farm_id(FK), name, area_mu, current_crop, status, notes, created_at |

### 7.2 向量数据库（Milvus）

**集合名**：`agro_agent_kb`

| 字段 | 类型 | 描述 |
|------|------|------|
| `id` | VARCHAR (主键) | 文档块唯一标识 |
| `vector` | FLOAT_VECTOR(1024) | text-embedding-v4 生成的向量 |
| `text` | VARCHAR | 文本内容 |
| `metadata` | JSON | 元数据（来源、分类、页码等） |

**索引配置**：

- 索引类型：HNSW
- 相似度度量：COSINE
- 向量维度：1024
- M（每个节点的连接数）：16
- efConstruction（构建时搜索深度）：200

---

## 8. RAG 检索增强生成管线

RAG 管线在 `app/core/vector_store.py` 中实现，采用 **三阶段混合检索** 策略：

```
用户查询
    │
    ▼
┌──────────────────────────────────────┐
│ Stage 1: 向量检索 (Milvus)           │
│ • text-embedding-v4 生成查询向量      │
│ • HNSW 近似最近邻搜索                 │
│ • 返回 Top-N 候选文档                 │
└──────────────────┬───────────────────┘
                   │
                   ▼
┌──────────────────────────────────────┐
│ Stage 2: 混合融合 (BM25 + Vector)    │
│ • BM25 稀疏检索（rank_bm25）         │
│ • Reciprocal Rank Fusion (RRF) 合并  │
│ • 融合密集与稀疏检索结果              │
└──────────────────┬───────────────────┘
                   │
                   ▼
┌──────────────────────────────────────┐
│ Stage 3: 重排序 (Reranker)           │
│ • DashScope gte-rerank-v2           │
│ • Cross-encoder 精排                 │
│ • 返回 Top-K 最终结果                │
└──────────────────┬───────────────────┘
                   │
                   ▼
            注入 LLM 上下文
```

**配置参数**（可通过 `.env` 调整）：

| 参数 | 默认值 | 描述 |
|------|--------|------|
| `RAG_TOP_K` | 10 | 初始检索数量 |
| `RAG_CHUNK_SIZE` | 512 | 文档分块大小（字符数） |
| `RAG_HYBRID_SEARCH` | true | 是否启用混合检索 |
| `RAG_RERANKER_ENABLED` | true | 是否启用重排序 |
| `RAG_RERANKER_TOP_K` | 5 | 重排序后保留数量 |

---

## 9. Agent 系统架构

### 9.1 LangGraph 核心状态图

Agent 系统的核心是基于 **LangGraph** 构建的状态图，采用 **Skill-first, Plan-Execute-Replan** 模式。

状态图定义在 `app/agents/graph.py`：

```
                          ┌─────────────────────────────────────┐
                          │                                     │
                          ▼                                     │
                    ┌───────────┐                               │
               ┌───▶│SkillRouter│                               │
               │    └─────┬─────┘                               │
               │          │                                     │
               │    ┌─────┴──────────────┐                      │
               │    │                    │                      │
               │    ▼                    ▼                      │
               │ ┌────────┐        ┌───────────┐               │
               │ │  END   │        │ ForkSkill │──▶ END        │
               │ │(域外拒绝)│       └───────────┘               │
               │ └────────┘                                    │
               │          │                                    │
               │          ▼                                    │
               │    ┌───────────┐                               │
               │    │  Planner  │                               │
               │    └─────┬─────┘                               │
               │          │                                    │
               │          ▼                                    │
               │    ┌───────────┐                               │
               │    │ Executor  │                               │
               │    └─────┬─────┘                               │
               │          │                                    │
               │          ▼                                    │
               │    ┌───────────┐                               │
               │    │Replanner  │───────┐                       │
               │    └───────────┘       │                       │
               │          │             │                       │
               │    ┌─────┴─────┐       │                       │
               │    │           │       │                       │
               │    ▼           ▼       ▼                       │
               │  [继续]     [完成]  [重路由]                    │
               │  (回到      (生成   (切换                      │
               │  Executor)  报告)   Skill)─────────────────────┘
               │              │
               │              ▼
               │            END
               │
               └── (reroute 时跳转到新 Skill)
```

**边的条件逻辑**：

1. **SkillRouter → Planner/ForkSkill/END**：
   - 域外输入 → 直接 END（返回拒绝消息）
   - Fork 类型 Skill → ForkSkill → END
   - 正常 Skill → Planner

2. **Replanner → Executor/END**：
   - `is_finished = true` → 生成报告 → END
   - `is_finished = false` 且有新计划 → Executor（继续执行）
   - `pending_reroute` → 重路由到新 Skill

3. **循环终止条件**：
   - 响应已生成（`response` 非空）
   - 计划为空
   - 达到最大步数（`MAX_AGENT_STEPS`）

### 9.2 五大 Agent 节点详解

#### 9.2.1 SkillRouter（技能路由）

**文件**：`app/agents/skill_router.py`

**职责**：接收用户输入，决定由哪个 Skill 处理。

**工作机制**：

1. **LLM 分类**：使用 qwen-turbo 模型，通过结构化输出（`SkillChoice` Schema）进行分类
2. **技能匹配**：从 `SkillRegistry` 中选择最佳匹配的 Skill
3. **协作检测**：通过关键词模式匹配检测是否需要多技能协作
4. **规则降级**：LLM 失败时，使用关键词匹配作为 fallback

**结构化输出 Schema**：

```python
class SkillChoice(BaseModel):
    skill_name: str          # 选中的技能名称
    reason: str              # 选择理由
    is_in_scope: bool        # 是否属于农业领域
    needs_collaboration: bool # 是否需要多技能协作
    collaboration_skills: list[str]  # 协作技能列表
```

**协作检测模式**（`_COLLABORATION_PATTERNS`）：

| 模式 | 技能组合 | 示例 |
|------|----------|------|
| weather + pest | 天气 + 病虫害 | "明天适合打药吗？" |
| weather + agriculture | 天气 + 农事 | "最近天气适合播种吗？" |
| pest + agriculture | 病虫害 + 农事 | "小麦病害防治方案" |
| weather + pest + agriculture | 三技能协作 | "雨后小麦病害防治" |

#### 9.2.2 Planner（计划生成）

**文件**：`app/agents/planner.py`

**职责**：根据 Skill 的 Playbook 和用户输入生成执行计划。

**工作机制**：

1. 获取选定 Skill 的 Playbook（Markdown 格式的操作指南）
2. 使用 LLM 生成 2-3 步的执行计划
3. 协作查询时合并多个 Skill 的 Playbook
4. LLM 返回空时使用 fallback 计划

**结构化输出 Schema**：

```python
class Plan(BaseModel):
    steps: list[str]  # 执行步骤列表，如 ["查询天气数据", "分析天气对病虫害的影响", "生成建议"]
```

#### 9.2.3 Executor（计划执行）

**文件**：`app/agents/executor.py`

**职责**：逐步执行计划中的步骤。

**工作机制**：

1. 从 `plan[0]` 弹出当前步骤
2. 根据 Skill 的 `allowed_tools` 白名单过滤可用工具
3. 两种执行模式：
   - **并行模式**（默认）：调用 `run_parallel_agent`，支持工具并行执行
   - **串行模式**（fallback）：使用 `langchain.agents.create_agent`
4. 执行结果通过 `operator.add` reducer 追加到 `past_steps`

**工具过滤**：每个 Skill 定义了 `allowed_tools` 列表，Executor 只暴露这些工具给 LLM。

#### 9.2.4 Replanner（重规划）

**文件**：`app/agents/replanner.py`

**职责**：评估执行进度，决定下一步行动。

**三种决策**：

1. **继续（Continue）**：生成新的计划，回到 Executor 继续执行
2. **完成（Finish）**：生成最终报告，流程结束
3. **重路由（Reroute）**：切换到另一个 Skill 重新开始

**结构化输出 Schema**：

```python
class Act(BaseModel):
    is_finished: bool
    plan: Plan | None           # 继续时的新计划
    response: str | None        # 完成时的最终响应
    pending_reroute: bool       # 是否需要重路由
    reroute_skill: str | None   # 重路由目标 Skill
    reroute_reason: str | None  # 重路由原因
```

**安全门控**：

| 门控 | 规则 | 目的 |
|------|------|------|
| 最大重路由次数 | 1 次 | 防止无限循环 |
| 最小已执行步数 | 2 步 | 确保有足够上下文 |
| 已尝试技能黑名单 | 已试过的 Skill 不可再路由 | 防止来回切换 |

**快速路径**：当计划剩余步数充足且上一步成功时，跳过 LLM 调用直接继续执行。

**报告生成**：最终报告可使用更高质量的 `report_model` 进行润色。

#### 9.2.5 ForkSkill（子图运行器）

**文件**：`app/agents/fork_runner.py`

**职责**：为标记为 `context: fork` 的 Skill 运行独立子图。

**工作机制**：

1. 复用 `build_aiops_graph()` 构建完整的子图
2. 设置 `state.inside_fork = True` 防止递归 Fork
3. 子图独立运行完整的 Plan-Execute-Replan 循环
4. 仅返回最终结果给主图

**当前状态**：所有 7 个 Skill 均使用 `inline` 模式，Fork 模式为未来长时间运行任务预留。

### 9.3 Agent 状态定义

**文件**：`app/agents/state.py`

```python
class PlanExecuteState(TypedDict):
    # 输入
    input: str                          # 用户输入
    selected_skill: str                 # 选中的 Skill 名称
    skill_reason: str                   # 选择理由

    # 计划
    plan: list[str]                     # 待执行步骤列表

    # 执行记录
    past_steps: Annotated[list, operator.add]  # 已执行步骤及结果（追加模式）

    # 输出
    response: str                       # 最终响应

    # 控制
    iteration: int                      # 当前迭代次数
    permission_mode: str                # 权限模式

    # 状态追踪
    transition_history: Annotated[list, operator.add]  # 状态转换历史
    inside_fork: bool                   # 是否在 Fork 子图中
    reroute_count: int                  # 重路由次数
    tried_skills: Annotated[list, operator.add]  # 已尝试的 Skill 列表
    pending_reroute: bool               # 待执行重路由
    reroute_skill: str                  # 重路由目标 Skill
    reroute_reason: str                 # 重路由原因

    # 协作
    collaboration_skills: list[str]     # 协作 Skill 列表
    collaboration_context: dict         # 协作上下文
```

### 9.4 Agent Harness（运行时管理器）

**文件**：`app/runtime/agent_harness.py`

Agent Harness 是整个 Agent 系统的**中央配置与管理单例**，职责包括：

#### Prompt 管理

包含所有 Agent 节点的系统提示词模板：

| Agent | Prompt 用途 |
|-------|------------|
| SkillRouter | 技能分类与路由决策 |
| Planner | 计划生成指导 |
| Executor | 工具使用与步骤执行 |
| Replanner | 进度评估与决策 |
| Report Writer | 最终报告生成 |
| RAG Chat | 知识库问答 |

#### 模型选择

每个 Agent 角色可独立配置 LLM 模型：

```python
router_model: str    # 路由模型（默认 qwen-turbo，快速低成本）
planner_model: str   # 计划模型
executor_model: str  # 执行模型（默认 qwen-max，高质量）
report_model: str    # 报告模型（用于最终润色）
```

#### 预算管理

- Token 预算评估
- 时间预算评估
- 预算超限处理

#### 错误分类

对 Agent 执行过程中的错误进行分类，决定是否重试、降级或终止。

#### 快速路径决策

在调用 LLM 之前进行预判，跳过不必要的 LLM 调用以降低成本和延迟。

---

## 10. 多 Agent 编排模式

AgroAgentOS 实现了 **7 种** 多 Agent 编排模式，从简单到复杂依次为：

### 10.1 Skill-first 路由模式

**模式**：单入口分发

```
用户输入 → SkillRouter → Skill A / Skill B / Skill C / ...
```

**实现**：

- Skills 以 `SKILL.md` 文件定义（YAML frontmatter + Markdown playbook）
- 位于 `app/skills/definitions/<skill_name>/SKILL.md`
- 启动时由 `SkillRegistry`（`@lru_cache` 单例）加载
- 支持 **7 个内置 Skill**：

| Skill | 描述 | 核心能力 |
|-------|------|----------|
| `agriculture_qa` | 农业综合问答 | RAG 检索 + 知识问答 |
| `weather_advice` | 天气咨询 | 天气查询 + 农事建议 |
| `pest_diagnosis` | 病虫害诊断 | 图像识别 + 症状分析 |
| `marketing_generator` | 营销内容生成 | 文案撰写 + 多平台适配 |
| `knowledge_retrieval` | 知识库检索 | 文档搜索 + 信息提取 |
| `generic_oncall` | 通用运维 | 系统监控 + 告警处理 |
| `crop_advisory` | 作物顾问 | 种植建议 + 生长管理 |

### 10.2 Plan-Execute-Replan 循环

**模式**：计划驱动的迭代执行

```
Planner → [Step 1] → Executor → Replanner → [Step 2] → Executor → Replanner → ... → 完成
```

**特点**：

- **动态规划**：每步执行后重新评估，支持计划调整
- **渐进式执行**：一次只执行一个步骤，降低出错影响
- **自适应终止**：响应已生成、计划为空或达到最大步数时终止

**循环流程**：

1. Planner 根据 Playbook 生成初始计划（2-3 步）
2. Executor 执行 `plan[0]`，结果追加到 `past_steps`
3. Replanner 评估进度：
   - 还有步骤且需要继续 → 生成新计划 → 回到 Executor
   - 信息充足 → 生成报告 → 结束
   - 方向错误 → 重路由到其他 Skill
4. 重复直到终止条件满足

### 10.3 Skill 协作（多技能联动）

**模式**：多 Skill 共同处理复合查询

```
用户: "明天适合打农药吗？"
  ↓
SkillRouter 检测到协作需求
  ↓
合并 weather_advice + pest_diagnosis 的 Playbook 和 Tools
  ↓
Planner 生成融合计划
  ↓
Executor 使用合并后的工具集执行
```

**协作检测机制**：

通过 `_COLLABORATION_PATTERNS` 关键词模式匹配：

```python
_COLLABORATION_PATTERNS = {
    ("weather", "pest"): ["打药", "施药", "喷药", "下雨.*药"],
    ("weather", "agriculture"): ["播种", "收割", "灌溉", "天气.*种"],
    ("pest", "agriculture"): ["病害.*作物", "虫害.*庄稼"],
    ("weather", "pest", "agriculture"): ["雨后.*病害.*防治"],
}
```

**支持的协作组合**：

| 组合 | 场景 |
|------|------|
| 双技能：weather + pest | 天气相关的病虫害防治 |
| 双技能：weather + agriculture | 天气相关的农事决策 |
| 双技能：pest + agriculture | 作物病虫害综合管理 |
| 三技能：weather + pest + agriculture | 复合农业决策 |

**执行时**：Playbook 合并、工具集合并，Executor 可调用所有参与 Skill 的工具。

### 10.4 Skill Reroute（技能重路由）

**模式**：Supervisor + Handoff（监督与转交）

```
Skill A → Planner → Executor → Replanner → 发现方向错误
                                              ↓
                                    重路由到 Skill B → 重新开始
```

**灵感来源**：LangGraph Supervisor + Handoff 模式

**安全门控机制**：

```python
# 重路由安全检查
if reroute_count >= 1:          # 最多重路由 1 次
    reject_reroute()
if len(past_steps) < 2:         # 至少执行 2 步才能重路由
    reject_reroute()
if target_skill in tried_skills: # 已尝试过的 Skill 不能再路由
    reject_reroute()
```

**验证方式**：安全检查在代码层面强制执行，不仅仅依赖 LLM 判断。

### 10.5 Fork 模式（子图隔离）

**模式**：独立子图执行

```
主图 → Skill (context: fork) → ForkSkill
                                    ↓
                            ┌──────────────┐
                            │  完整子图     │
                            │  Planner     │
                            │  Executor    │
                            │  Replanner   │
                            └──────────────┘
                                    ↓
                              返回最终结果 → 主图继续
```

**特点**：

- 子图复用 `build_aiops_graph()` 构建，共享相同的状态图结构
- `inside_fork = True` 标记防止递归 Fork
- 子图完全隔离，内部状态不泄露到主图
- 适用于长时间运行的复杂任务

**当前状态**：所有 7 个 Skill 使用 `inline` 模式，Fork 模式已实现但未启用。

### 10.6 Subagent 委托

**模式**：工具级别的子 Agent 委托

```
Executor → 工具列表中发现 delegate_to_xxx → 子 Agent (ReAct Loop)
                                                    ↓
                                              独立工具白名单
                                              独立异常隔离
                                                    ↓
                                              返回结果字符串
```

**文件**：`app/agents/subagents/runner.py`

**特点**：

- Subagent 以 `delegate_to_<agent_type>` 工具的形式暴露给 Executor
- 每个 Subagent 运行独立的 `run_parallel_agent` ReAct 循环
- 拥有独立的工具白名单
- 异常隔离：Subagent 失败返回错误字符串，不抛出异常影响主流程

### 10.7 并行工具执行

**模式**：工具级别的并行优化

```
工具调用序列: [read_a, read_b, write_c, read_d, read_e]
                ↓
批次划分:     [read_a, read_b] | [write_c] | [read_d, read_e]
                ↓               ↓            ↓
执行方式:    asyncio.gather   串行执行    asyncio.gather
```

**文件**：`app/runtime/tool_runner.py`

**机制**：

1. 工具通过 `ToolMeta.concurrency_safe` 标记是否可并发
2. 相邻的只读工具被划分为同一批次，通过 `asyncio.gather` 并行执行
3. 写工具强制创建新的串行批次
4. 每批次最大并行度：6（可配置）
5. 工具结果截断到 `max_result_chars`，防止上下文溢出

---

## 11. Skill 技能系统

### 技能定义格式

每个 Skill 是一个目录，包含 `SKILL.md` 文件：

```
app/skills/definitions/
├── agriculture_qa/
│   └── SKILL.md
├── weather_advice/
│   └── SKILL.md
├── pest_diagnosis/
│   └── SKILL.md
└── ...
```

`SKILL.md` 格式：

```markdown
---
name: weather_advice
description: 天气咨询与农业气象建议
context: inline          # inline | fork
allowed_tools:           # 允许使用的工具白名单
  - weather_query
  - knowledge_search
  - web_search
triggers:                # 触发关键词
  - 天气
  - 气象
  - 温度
  - 降雨
---

# 天气咨询技能

## 操作指南 (Playbook)

1. 查询目标地区的天气数据
2. 分析天气对农事活动的影响
3. 生成农业气象建议
...
```

### 技能注册表

**文件**：`app/skills/registry.py`

- 启动时扫描 `definitions/` 目录，解析所有 `SKILL.md`
- 解析 YAML frontmatter 获取元数据
- 提取 Markdown body 作为 Playbook
- 以 `@lru_cache` 单例模式运行
- 提供 `get_skill(name)`、`list_skills()`、`match_skill(query)` 等方法

---

## 12. MCP 工具服务器

MCP（Model Context Protocol）是外部工具的标准协议，AgroAgentOS 通过 MCP 接入多种外部能力。

### MCP 服务器列表

| 服务器 | 文件 | 端口 | 功能 |
|--------|------|------|------|
| Weather MCP | 天气服务 | 8010 | 天气数据查询 |
| WebSearch MCP | 网络搜索 | 8006 | 联网搜索 |
| Docker MCP | docker_server.py | - | Docker 容器管理 |
| Network MCP | network_server.py | - | 网络诊断 |
| System MCP | system_server.py | - | 系统资源监控 |
| WinLog MCP | winlog_server.py | - | Windows 事件日志 |

### MCP 加载流程

```
应用启动
    ↓
MCP Loader (app/core/mcp_loader.py)
    ↓
连接各 MCP Server 端点
    ↓
通过 langchain-mcp-adapters 转换为 LangChain Tools
    ↓
注册到工具池，供 Executor 调用
```

---

## 13. 知识库系统

### 知识文档结构

```
knowledge_base/
├── planting/           # 种植技术
│   ├── rice.md
│   ├── wheat.md
│   └── corn.md
├── pest_control/       # 病虫害防治
│   ├── rice_blast.md
│   ├── aphid.md
│   └── ...
├── soil/               # 土壤管理
│   ├── soil_health.md
│   └── ...
└── weather/            # 气象知识
    ├── frost.md
    └── ...
```

共 **11 篇** 农业知识文档，覆盖 4 大类别。

### 知识入库流程

```
Markdown 文档
    ↓
scripts/ingest_agriculture_kb.py
    ↓
文本分块（chunk_size: 512 字符）
    ↓
DashScope text-embedding-v4 生成向量（1024 维）
    ↓
写入 Milvus 集合 agro_agent_kb
```

### 文档管理 API

- `POST /api/v1/documents/upload`：上传新文档
- `GET /api/v1/documents`：列出所有文档
- `DELETE /api/v1/documents/{id}`：删除文档

上传的文档会自动触发入库流程。

---

## 14. 服务端口与部署架构

### 端口分配

| 服务 | 端口 | 协议 | 描述 |
|------|------|------|------|
| FastAPI 应用 | 9800 | HTTP | 主应用服务 |
| Milvus gRPC | 19530 | gRPC | 向量数据库 |
| Milvus REST | 9091 | HTTP | 向量数据库 REST API |
| MinIO Console | 9001 | HTTP | 对象存储管理界面 |
| Attu | 8000 | HTTP | Milvus Web UI |
| Redis | 6379 | TCP | 缓存/会话存储 |
| open-webSearch | 3210 | HTTP | 联网搜索服务 |
| Weather MCP | 8010 | HTTP | 天气查询服务 |
| WebSearch MCP | 8006 | HTTP | 网络搜索服务 |

### Docker Compose 服务编排

**文件**：`docker-compose.yml`

```yaml
services:
  etcd:           # Milvus 依赖（v3.5.5）
  minio:          # Milvus 对象存储
  standalone:     # Milvus 向量数据库（v2.4.10）
  attu:           # Milvus Web 管理界面（v2.4）
  redis:          # 会话缓存（7-alpine）
  open-websearch: # 联网搜索服务（Node.js）
```

所有服务位于 `agro_network` 网络。

### 架构拓扑

```
                    ┌─────────────────────────┐
                    │      Nginx (可选)        │
                    │    反向代理 + SSL        │
                    └────────────┬────────────┘
                                 │
                    ┌────────────┴────────────┐
                    │     FastAPI :9800        │
                    │  (静态文件 + API + SSE)  │
                    └────────────┬────────────┘
                                 │
          ┌──────────┬───────────┼───────────┬──────────┐
          │          │           │           │          │
    ┌─────┴─────┐ ┌──┴───┐ ┌────┴────┐ ┌────┴────┐ ┌───┴────┐
    │  Milvus   │ │Redis │ │  MySQL  │ │Weather  │ │WebSearch│
    │ :19530    │ │:6379 │ │(可选)   │ │MCP:8010 │ │MCP:8006│
    └─────┬─────┘ └──────┘ └─────────┘ └─────────┘ └────────┘
          │
    ┌─────┴─────┐
    │   MinIO   │
    │  :9001    │
    └───────────┘
```

---

## 15. 部署方案

### 开发环境

```bash
# 1. 安装 Python 依赖
pip install -r requirements.txt

# 2. 启动基础设施服务
docker compose up -d    # Milvus, Redis, MinIO, open-webSearch

# 3. 配置环境变量
cp .env.example .env
# 编辑 .env 填入 API Key 等配置

# 4. 启动后端
python -m app.main
# 或
uvicorn app.main:app --reload --port 9800

# 5. 启动前端（开发模式）
cd frontend-react
npm install
npm run dev
```

### Windows 环境

```powershell
# 一键启动
.\run.ps1

# 一键停止
.\run.ps1 -Stop
```

### 生产环境（Linux + BaoTa 面板）

```bash
# 一键部署
chmod +x deploy.sh
./deploy.sh
```

部署脚本自动完成 10 个步骤：

1. 检测系统环境（apt/yum/dnf）
2. 安装系统依赖
3. 安装 Python 3.11
4. 创建虚拟环境
5. 安装 pip 依赖
6. 配置环境变量
7. 构建前端（`npm run build`）
8. 初始化数据库
9. 导入知识库
10. 配置 systemd 服务 + Nginx 反向代理

### 生产环境（手动）

```bash
# 1. 构建前端
cd frontend-react && npm run build && cd ..

# 2. 启动基础设施
docker compose up -d

# 3. 启动应用（FastAPI 自动服务前端静态文件）
uvicorn app.main:app --host 0.0.0.0 --port 9800 --workers 4
```

### 静态文件服务

FastAPI 自动将 `frontend-react/dist/` 挂载为静态文件目录，并配置 SPA fallback（所有非 API 路由返回 `index.html`）。

---

## 附录：技术选型决策

| 决策点 | 选择 | 理由 |
|--------|------|------|
| Web 框架 | FastAPI | 异步高性能，自动 OpenAPI 文档，原生 SSE 支持 |
| Agent 编排 | LangGraph | 基于图的灵活编排，支持条件分支和循环 |
| 向量数据库 | Milvus | 高性能向量检索，支持 HNSW 索引 |
| 前端框架 | React 19 | 生态成熟，TypeScript 支持好 |
| 状态管理 | Zustand | 轻量级，TypeScript 友好，无 boilerplate |
| 构建工具 | Vite | 极速 HMR，原生 ESM 支持 |
| CSS 方案 | TailwindCSS | 原子化 CSS，开发效率高 |
| LLM 提供商 | DashScope (通义千问) | 国内访问稳定，中文能力强 |
| 数据库 | SQLite/MySQL 双模式 | 开发零配置，生产高性能 |
| 地图 | Leaflet | 开源免费，功能丰富 |

---

*本文档由代码分析自动生成，如有疑问请参考源码或联系项目维护者。*
