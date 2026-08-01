# Remove AIOps Legacy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove server-operations/AIOps functionality while preserving agricultural chat, agricultural skills, farms, weather, market, pest diagnosis, and image analysis.

**Architecture:** The public FastAPI surface becomes agriculture-only. The reusable LangGraph orchestration remains, but its interface and fallback skill become agriculture-specific. RAG history uses the canonical history module; Redis stores only session memory. SRE-only adapters, scripts, SOPs, and Prometheus corpus are removed.

**Tech Stack:** FastAPI, LangGraph, SQLAlchemy, Redis, pytest, React/Vite.

## Global Constraints

- Preserve existing user changes in the dirty worktree.
- Do not drop database tables while the Alembic revision chain is broken.
- Keep `pest_diagnosis`, `/chat/stream`, `/image/analyze`, farm, weather, market, auth, session, document, history, skill, and video functionality.
- Remove `/aiops`, `/webhook`, `/diagnosis`, and AIOps-only observability routes.

---

### Task 1: Lock the agriculture-only public surface

**Files:**
- Create: `tests/api/test_agriculture_surface.py`
- Modify: `app/main.py`

**Interfaces:**
- Produces: FastAPI routes without AIOps, Alertmanager, or duplicate diagnosis-record endpoints.

- [ ] Write a test that imports the real FastAPI app, asserts agriculture routes exist, and asserts removed route prefixes do not exist.
- [ ] Run the test and confirm it fails because the AIOps routes are still registered.
- [ ] Remove AIOps router imports and registrations.
- [ ] Run the test and confirm it passes.

### Task 2: Remove the AIOps state and recording path

**Files:**
- Delete: `app/api/v1/aiops.py`, `app/api/v1/webhook.py`, `app/api/v1/diagnosis.py`, `app/api/v1/observability.py`
- Delete: `app/services/aiops_service.py`, `app/services/diagnosis_recorder.py`
- Delete: `app/schemas/aiops.py`
- Modify: `app/services/rag_service.py`, `app/services/chat_memory.py`, `app/services/rag/web_context.py`, `app/runtime/agent_harness.py`

**Interfaces:**
- Consumes: `history_service.add_record(...)`.
- Produces: agriculture chat history with no cross-session AIOps report context.

- [ ] Add a focused history test if existing behavior lacks coverage.
- [ ] Replace `diagnosis_recorder.record_diagnosis` with `history_service.add_record`.
- [ ] Remove global diagnosis-report Redis methods and all callers.
- [ ] Remove `diagnosis_context` and `extra_reports` from RAG prompt/query interfaces.
- [ ] Delete AIOps-only modules and rerun focused tests.

### Task 3: Agriculture-name the retained graph

**Files:**
- Modify: `app/agents/__init__.py`, `app/agents/graph.py`, `app/agents/fork_runner.py`, `app/agents/skill_router.py`, `app/agents/planner.py`
- Modify: `app/skills/registry.py`, `app/skills/__init__.py`, `app/runtime/agent_harness.py`
- Delete: `app/skills/definitions/generic_oncall/SKILL.md`
- Delete: `app/agents/subagents/*`
- Modify: `app/tools/mcp_loader.py`

**Interfaces:**
- Produces: `build_agriculture_graph()` and default skill `agriculture_qa`.

- [ ] Add tests for the agriculture graph export and registry fallback.
- [ ] Confirm tests fail against `build_aiops_graph` and `generic_oncall`.
- [ ] Rename the graph interface and fallback semantics.
- [ ] Remove SRE subagent delegate tools from the tool loader.
- [ ] Run graph, registry, and tool tests.

### Task 4: Remove SRE assets and agriculture-scope web search

**Files:**
- Delete: SRE-only files under `mcp_servers/`, `scripts/`, `docs/sop/`, and `data/kb_corpus/awesome-prometheus-alerts/`
- Modify: `mcp_servers/websearch_server.py`, `app/config.py`, `.env.example`, `requirements.txt`
- Modify or delete: AIOps-only documents found by the final reference scan.

**Interfaces:**
- Produces: agriculture-scoped web search and an agriculture-only repository corpus.

- [ ] Add a test that agricultural queries pass the web-search policy while unrelated entertainment queries remain blocked.
- [ ] Confirm the agricultural weather query fails before policy changes.
- [ ] Update policy copy and keyword configuration.
- [ ] Delete exact verified SRE-only asset paths.
- [ ] Run focused tests.

### Task 5: Verify the complete cleanup

**Files:**
- Modify only files required by failures discovered in verification.

**Interfaces:**
- Produces: an importable backend and buildable frontend with no active AIOps references.

- [ ] Run `pytest tests -q` with an explicit valid debug environment.
- [ ] Run `npm run build` in `frontend-react/`.
- [ ] Scan active code and docs for `aiops`, `alertmanager`, `generic_oncall`, `OnCall`, Prometheus corpus references, and AIOps Redis keys.
- [ ] Inspect `git diff --check` and `git status --short`.
- [ ] Record any intentionally retained historical migration/table names as residual data, not active AIOps functionality.
