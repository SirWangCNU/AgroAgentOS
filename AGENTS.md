# AgroAgentOS

FastAPI + LangGraph multi-agent agriculture platform. Python 3.11+ backend, React 19 + Vite frontend.

## 编码规范（强制）

人类开发者和 AI 编码助手在编写或修改代码前，必须阅读并遵守 [`docs/DEVELOPMENT_STANDARDS.md`](docs/DEVELOPMENT_STANDARDS.md)。

AI 必须先检查现有实现、相邻测试和 `git status`，再以最小范围修改代码；必须遵守项目分层、类型、错误处理和测试规则。禁止覆盖用户改动、顺手重构无关代码、提交敏感信息、绕过类型或迁移、吞掉异常、删除或弱化测试。完成后必须运行与改动相关的验证，并如实报告结果。

## Commands

### Backend
```bash
# Install deps
pip install -r requirements.txt

# Start (pick one)
uvicorn app.main:app --reload --port 9800   # dev with hot-reload
python -m app.main                           # uses Settings host/port defaults

# DB migrations
alembic upgrade head
alembic revision --autogenerate -m "description"

# Tests (no pytest.ini, uses defaults)
pytest
```

### Frontend (`frontend-react/`)
```bash
npm ci               # install (use ci, not install)
npm run dev          # port 3000, proxies /api -> :9800
npm run build        # tsc -b && vite build
npm run lint         # ESLint (flat config)
npm run dev:fresh    # clean caches + dev
npm run build:fresh  # clean caches + build
```

### Infrastructure
```bash
docker compose up -d   # Milvus (19530), Redis (6379), Attu (8000), MinIO (9001), open-webSearch (3210)
```

### Windows one-click launcher
```powershell
.\run.ps1                    # start all
.\run.ps1 -Stop              # stop all
.\run.ps1 -NoMilvus          # skip Milvus
.\run.ps1 -NoRedis           # skip Redis
.\run.ps1 -NoFrontend        # skip frontend dev server
.\run.ps1 -Logs              # tail logs
```

## Architecture

### Backend layers (`app/`)
- `api/v1/` — 16 FastAPI routers, all mounted under `/api/v1`
- `api/deps.py` — dependency injection (`get_current_user`, `require_admin`)
- `services/` — business logic (no direct DB calls from routers)
- `core/` — infra adapters: `database.py` (SQLite/MySQL), `milvus.py`, `redis.py`, `llm.py`, `mcp_client.py`, `hybrid_retriever.py`, `reranker.py`
- `models/` — Pydantic domain models
- `schemas/` — Pydantic request/response schemas; `common.py` defines unified `ApiResponse[T]`
- `exceptions.py` — custom `AppException` hierarchy caught by global handlers

### Agent system (`app/agents/`)
Graph: `START → SkillRouter → Planner → Executor → Replanner → (loop | END)`

- `state.py` — `PlanExecuteState` TypedDict with `operator.add` reducers
- `skill_router.py` — LLM-based skill selection
- `planner.py` — LLM-based plan generation
- `executor.py` — tool execution via `runtime/tool_runner.py`
- `replanner.py` — replanning with failure memory (`tried_skills`)
- `fork_runner.py` — independent sub-graph execution for `fork` mode skills

### Skills (`app/skills/definitions/<name>/SKILL.md`)
Each skill is a YAML-frontmatter + Markdown playbook file. Fields: `name`, `triggers`, `allowed_tools`, `risk_level`, `context`. Loaded at startup by `SkillRegistry` singleton. Two execution modes: `inline` (playbook injected into main graph) and `fork` (independent sub-graph).

### Config (`app/config.py`)
- Pydantic Settings singleton via `@lru_cache`
- Loads from `.env` at project root (copy `.env.example`)
- `case_sensitive=False` — env vars can be uppercase or lowercase
- Required: `DASHSCOPE_API_KEY`
- Toggle DB: `USE_SQLITE=true` (default) or `false` (MySQL)
- LLM fallback: DashScope → DeepSeek (if model name starts with "deepseek") → local Ollama

### RAG pipeline
- Hybrid search: BM25 + Milvus vector + RRF fusion
- Reranker: DashScope `gte-rerank-v2`
- Embedding: DashScope `text-embedding-v4` (1024 dim)
- Knowledge base docs in `knowledge_base/`, ingested via `scripts/ingest_agriculture_kb.py`

### Tools
MCP protocol via `langchain-mcp-adapters` + `fastmcp`. Tool implementations in `app/tools/`. MCP servers in `mcp_servers/`.

## Frontend (`frontend-react/src/`)

- **State**: Zustand stores (`stores/auth.ts`, `conversation.ts`, `health.ts`, `ui.ts`)
- **Server state**: TanStack React Query v5
- **API client**: `api/client.ts` — `authFetch` wrapper auto-redirects on 401; `consumeSSE` async generator for SSE streaming
- **Routing**: react-router-dom v7, routes defined in `App.tsx`
- **Styling**: Tailwind CSS v4 via Vite plugin
- **Maps**: Leaflet + React-Leaflet
- **Markdown**: react-markdown + remark-gfm for AI responses

## Gotchas

- **No Python linter/formatter configured** — no ruff, black, pyproject.toml, or .editorconfig
- **No CI/CD** — no GitHub Actions or similar pipelines exist
- **Chinese docstrings and comments** throughout the codebase
- **No typecheck command for frontend** — `tsc -b` only runs as part of `npm run build`
- **`tests/api/` is empty** — all real tests live in `tests/services/`
- **Script-level tests** in `scripts/` (e.g., `test_phase1.py`) are integration/smoke tests run outside pytest
- **`_json` suffix pattern** — ORM models store structured data as JSON text columns (e.g., `extra_json`) with `@property` auto-parsing accessors
- **Frontend build served by FastAPI** — in production, FastAPI mounts `frontend-react/dist/` as static files
- **Vite proxies `/api` to `:9800`** — frontend dev server must be running alongside backend
