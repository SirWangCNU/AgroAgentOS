# Farm Agent Direct Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将遗留 AIOps 执行链直接改写为面向比赛演示的 Farm Agent，交付“AI 农场巡检 → 有证据的行动提案 → 人工批准 → 任务执行 → AI 复核”的可审计闭环。

**Architecture:** 保留现有 LangGraph `SkillRouter → Planner → Executor → Replanner` 节点算法与 SSE 执行能力，但彻底替换 AIOps 路由、服务、Schema、Skill、二级 Agent 和文案。所有农场资源访问以已认证用户和 `FarmRunContext` 为安全边界；Agent 只能写提案和复核草稿，批准、完成、退回仍由普通业务 API 执行。

**Tech Stack:** Python 3.11、FastAPI、Pydantic v2、SQLAlchemy/Alembic、LangGraph、LangChain tools、pytest；React 19、TypeScript、Vite、TanStack React Query v5、Zustand、Tailwind CSS v4。

## Global Constraints

- 开始每个任务前重新检查 `git status --short`，保留用户已有改动，不顺手重构无关文件。
- 后端遵守 `router → service → model/core` 分层；路由不得直接操作数据库。
- 所有新 ORM 结构由 Alembic 迁移创建，同时兼容 SQLite 与 MySQL；不得依赖 `Base.metadata.create_all()` 代替迁移。
- 跨用户访问统一返回 403，不通过错误差异泄露资源是否存在。
- Agent 工具不得接受模型提供的 `user_id`；身份只能来自 `FarmRunContext`。
- Agent 不得调用批准、拒绝、完成、退回、取消等最终决策操作。
- 历史 `source=aiops` 数据只读保留；新运行只写 `source=farm_agent`；不保留 `/api/v1/aiops/*` 兼容入口。
- 结构化提案和复核结论必须来自 Pydantic 校验后的对象，不从 Markdown 反向解析。
- 每项实现按“先失败测试、再最小实现、再通过测试”执行；每个任务形成独立提交。
- 前端当前无测试框架，不额外引入依赖；通过 `npm run lint`、`npm run build` 和最终手工闭环验证。

---

## Task 1: 建立提案、任务和运行记录的数据契约

**Files:**

- Create: `app/models/farm_agent.py`
- Create: `app/schemas/farm_agent.py`
- Create: `app/schemas/diagnosis.py`
- Create: `alembic/versions/007_add_farm_agent_workflow.py`
- Modify: `app/core/sqlite.py: AgentRun`
- Modify: `app/models/__init__.py`
- Modify: `app/api/v1/diagnosis.py: imports`
- Test: `tests/models/test_farm_agent_models.py`
- Test: `tests/schemas/test_farm_agent_schemas.py`

- [ ] **Step 1: 写 ORM 和 JSON 属性的失败测试**

  在 `tests/models/test_farm_agent_models.py` 用独立内存 SQLite engine 创建元数据，断言：

  - `FarmActionProposal.status` 默认 `pending`；
  - `FarmTask.status` 默认 `pending`；
  - `evidence`、`actions`、`execution`、`agent_verdict`、`context_snapshot`、`outcome` 空值返回类型稳定；
  - setter 使用 `ensure_ascii=False`，中文往返不丢失；
  - `proposal_id`、`task_id` 和 `run_id` 唯一约束存在。

- [ ] **Step 2: 写 Schema 枚举和交叉字段校验的失败测试**

  在 `tests/schemas/test_farm_agent_schemas.py` 固定以下契约：

  ```python
  evidence = FarmEvidence(
      source_type="weather_forecast",
      source_id="demo-rainstorm-24h",
      summary="未来 24 小时累计降雨 82mm",
      observed_at="2026-07-18T08:00:00+08:00",
      fact_kind="measured",
      payload={"rainfall_mm": 82.0, "threshold_mm": 50.0},
  )
  action = ProposedAction(
      action_key="drainage-check-a1",
      title="检查 A1 地块排水沟",
      task_type="drainage",
      instructions="清理堵塞点并提交轨迹或文字记录",
      priority="urgent",
      field_id=1,
      assignee_name="现场作业员",
      due_at="2026-07-18T18:00:00+08:00",
      acceptance_criteria=["排水沟无明显堵塞", "提交执行说明"],
  )
  ```

  并断言非法 severity、priority、status、空证据、高置信度但只有 `inference` 证据均触发 `ValidationError`。

- [ ] **Step 3: 运行失败测试**

  Run: `pytest tests/models/test_farm_agent_models.py tests/schemas/test_farm_agent_schemas.py -q`

  Expected: FAIL，提示 `app.models.farm_agent` 或 `app.schemas.farm_agent` 不存在。

- [ ] **Step 4: 实现 ORM 与 Schema**

  `app/models/farm_agent.py` 创建两个 ORM：

  ```python
  class FarmActionProposal(Base):
      __tablename__ = "farm_action_proposals"

      id = Column(Integer, primary_key=True, autoincrement=True)
      proposal_id = Column(String(64), unique=True, nullable=False, index=True)
      farm_id = Column(Integer, ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True)
      created_by = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
      run_id = Column(String(64), ForeignKey("agent_runs.run_id"), nullable=False, index=True)
      risk_fingerprint = Column(String(64), nullable=False)
      title = Column(String(256), nullable=False)
      severity = Column(String(16), nullable=False)
      summary = Column(Text, nullable=False)
      confidence = Column(Float, nullable=False, default=0.0)
      evidence_json = Column(Text, nullable=False, default="[]")
      actions_json = Column(Text, nullable=False, default="[]")
      status = Column(String(16), nullable=False, default="pending", index=True)
      decision_note = Column(Text, nullable=False, default="")
      created_at = Column(DateTime, nullable=False, default=func.now())
      decided_at = Column(DateTime, nullable=True)

      __table_args__ = (
          UniqueConstraint("run_id", "risk_fingerprint", name="uq_proposal_run_risk"),
      )

  class FarmTask(Base):
      __tablename__ = "farm_tasks"

      id = Column(Integer, primary_key=True, autoincrement=True)
      task_id = Column(String(64), unique=True, nullable=False, index=True)
      proposal_id = Column(String(64), ForeignKey("farm_action_proposals.proposal_id"), nullable=True, index=True)
      action_key = Column(String(128), nullable=True)
      farm_id = Column(Integer, ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True)
      field_id = Column(Integer, ForeignKey("fields.id", ondelete="SET NULL"), nullable=True, index=True)
      assignee_name = Column(String(128), nullable=False, default="")
      title = Column(String(256), nullable=False)
      task_type = Column(String(64), nullable=False, index=True)
      instructions = Column(Text, nullable=False)
      acceptance_criteria_json = Column(Text, nullable=False, default="[]")
      priority = Column(String(16), nullable=False, default="normal")
      status = Column(String(16), nullable=False, default="pending", index=True)
      due_at = Column(DateTime, nullable=True)
      execution_json = Column(Text, nullable=False, default="{}")
      agent_verdict_json = Column(Text, nullable=False, default="{}")
      created_at = Column(DateTime, nullable=False, default=func.now())
      updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())

      __table_args__ = (
          UniqueConstraint("proposal_id", "action_key", name="uq_task_proposal_action"),
      )
  ```

  为 JSON 字段实现显式 getter/setter；解析异常记录 warning 并返回空结构，不吞掉业务写入异常。

  `app/schemas/farm_agent.py` 定义并统一复用：

  - `Severity = Literal["low", "medium", "high", "critical"]`
  - `ProposalStatus = Literal["pending", "approved", "rejected"]`
  - `TaskStatus = Literal["pending", "in_progress", "submitted", "returned", "completed", "cancelled"]`
  - `VerificationVerdict = Literal["pass", "needs_evidence", "rework", "manual_review"]`
  - `FarmEvidence`、`ProposedAction`、`ProposalDraft`、`ProposalResponse`
  - `FarmInspectionRequest(farm_id: int, objective: str = "请对当前农场执行综合巡检", demo_scenario: Literal["rainstorm"] | None = None)`
  - `FarmAgentEvent` 及事件 Literal；必须包含 `context_loaded`、`tool_call`、`proposal_created`
  - `ProposalApprovalRequest(actions: list[ProposedAction], decision_note: str)`
  - `ProposalRejectRequest(decision_note: str)`
  - `TaskSubmitRequest(note: str, trajectory_file_ids: list[int], attachment_urls: list[str])`
  - `TaskDecisionRequest(note: str)`
  - `TaskResponse`、`AgentRunTimelineResponse`

  把旧 `DiagnosisRecordRequest`、`ConversationRecordRequest`、`RecordResponse`、`RecordListResponse` 原样迁至 `app/schemas/diagnosis.py`，仅将 `DiagnosisRecordRequest.source` 默认值改为 `farm_agent`，说明允许 `farm_agent/chat/monitoring/aiops`。

- [ ] **Step 5: 扩展 AgentRun 并编写迁移**

  在 `app/core/sqlite.py: AgentRun` 添加：

  ```python
  user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
  farm_id = Column(Integer, ForeignKey("farms.id", ondelete="SET NULL"), nullable=True, index=True)
  run_type = Column(String(32), nullable=True, index=True)
  context_snapshot_json = Column(Text, nullable=True)
  outcome_json = Column(Text, nullable=True)
  ```

  添加 `context_snapshot`、`set_context_snapshot()`、`outcome`、`set_outcome()`，使用与 `transitions` 相同的 JSON 规则。

  `007_add_farm_agent_workflow.py` 必须：

  1. batch alter `agent_runs` 增加五列及索引；
  2. 创建 `farm_action_proposals` 和 `farm_tasks`；
  3. 创建上述 unique constraints 和查询索引；
  4. downgrade 先删子表，再删 AgentRun 索引和列。

- [ ] **Step 6: 更新导出与诊断接口引用**

  在 `app/models/__init__.py` 导入新模型，确保启动时 SQLAlchemy metadata 可见。把 `app/api/v1/diagnosis.py` 从 `app.schemas.aiops` 的导入改为 `app.schemas.diagnosis`；此时暂不删除旧 `schemas/aiops.py`。

- [ ] **Step 7: 验证并提交**

  Run: `pytest tests/models/test_farm_agent_models.py tests/schemas/test_farm_agent_schemas.py -q`

  Run: `alembic upgrade head`

  Run: `alembic downgrade 006_add_wx_binding && alembic upgrade head`

  Expected: tests PASS，迁移可正向和反向执行。

  Commit: `git add app/models/farm_agent.py app/schemas/farm_agent.py app/schemas/diagnosis.py app/core/sqlite.py app/models/__init__.py app/api/v1/diagnosis.py alembic/versions/007_add_farm_agent_workflow.py tests/models/test_farm_agent_models.py tests/schemas/test_farm_agent_schemas.py && git commit -m "feat: add farm agent workflow models"`

---

## Task 2: 建立不可伪造的 FarmRunContext

**Files:**

- Create: `app/runtime/farm_run_context.py`
- Test: `tests/runtime/test_farm_run_context.py`

- [ ] **Step 1: 写缺失上下文、嵌套恢复和并发隔离测试**

  测试固定以下接口：

  ```python
  context = FarmRunContext(user_id=7, farm_id=11, run_id="run-1", run_type="inspection")

  with bind_farm_run_context(context):
      assert require_farm_run_context() == context

  with pytest.raises(AppException) as exc_info:
      require_farm_run_context()
  assert exc_info.value.status_code == 500
  assert exc_info.value.code == "FARM_RUN_CONTEXT_MISSING"
  ```

  使用 `asyncio.gather()` 同时绑定两个不同用户/农场，断言每个协程只读到自己的上下文；再测内层 context 退出后恢复外层 context。

- [ ] **Step 2: 运行失败测试**

  Run: `pytest tests/runtime/test_farm_run_context.py -q`

  Expected: FAIL，模块不存在。

- [ ] **Step 3: 实现 ContextVar 生命周期**

  `app/runtime/farm_run_context.py` 提供：

  ```python
  @dataclass(frozen=True, slots=True)
  class FarmRunContext:
      user_id: int
      farm_id: int
      run_id: str
      run_type: Literal["inspection", "task_verification"]
      task_id: str | None = None
      demo_scenario: str | None = None

  def get_farm_run_context() -> FarmRunContext | None:
      return _farm_run_context.get()

  def require_farm_run_context() -> FarmRunContext:
      context = get_farm_run_context()
      if context is None:
          raise AppException(
              status_code=500,
              code="FARM_RUN_CONTEXT_MISSING",
              message="Farm Agent 运行上下文缺失",
          )
      return context

  @contextmanager
  def bind_farm_run_context(context: FarmRunContext) -> Iterator[FarmRunContext]:
      token = _farm_run_context.set(context)
      try:
          yield context
      finally:
          _farm_run_context.reset(token)
  ```

- [ ] **Step 4: 验证并提交**

  Run: `pytest tests/runtime/test_farm_run_context.py -q`

  Expected: PASS。

  Commit: `git add app/runtime/farm_run_context.py tests/runtime/test_farm_run_context.py && git commit -m "feat: add secure farm run context"`

---

## Task 3: 聚合农场快照和确定性风险证据

**Files:**

- Create: `app/services/farm_snapshot_service.py`
- Create: `app/services/farm_risk_service.py`
- Test: `tests/services/test_farm_snapshot_service.py`
- Test: `tests/services/test_farm_risk_service.py`

- [ ] **Step 1: 写所有权过滤和快照结构的失败测试**

  `tests/services/test_farm_snapshot_service.py` 以现有 `sqlite_manager` 测试 fixture 风格创建两个用户的农场、地块和轨迹，断言：

  ```python
  snapshot = farm_snapshot_service.get_snapshot(farm_id=owned_farm.id, user_id=owner.id)
  assert snapshot.farm.id == owned_farm.id
  assert {field.id for field in snapshot.fields} == {owned_field.id}
  assert snapshot.recent_trajectory_files[0].field_id == owned_field.id
  assert snapshot.pending_task_count == 1
  ```

  对另一个用户调用时断言 403，且错误消息不包含农场名称。

- [ ] **Step 2: 写暴雨阈值和降级行为的失败测试**

  `tests/services/test_farm_risk_service.py` 固定规则：未来 24 小时累计降雨 `>= 50mm` 产生 `high` 排水风险，`>= 80mm` 产生 `critical` 风险；天气不可用时返回 `degraded=True` 且不得生成气象类高置信度风险。

  轨迹质量固定规则：`depth_std > 5` 或 `work_area_mu / field.area_mu < 0.8` 产生 `medium` 作业质量风险。每项风险必须含 `risk_key`、`severity`、`confidence`、`evidence`、`suggested_actions`。

- [ ] **Step 3: 运行失败测试**

  Run: `pytest tests/services/test_farm_snapshot_service.py tests/services/test_farm_risk_service.py -q`

  Expected: FAIL，服务模块不存在。

- [ ] **Step 4: 实现只读快照服务**

  `farm_snapshot_service.get_snapshot(farm_id: int, user_id: int) -> FarmSnapshot` 必须先调用 `farm_service.get_farm()`，再在一次只读 session 中加载：

  - 农场基础字段；
  - 所有地块、作物、生长阶段、边界；
  - 每地块最近 3 个 `TrajectoryFile`；
  - 同农场未终止任务计数；
  - `captured_at` 和 `data_gaps`。

  返回 Pydantic DTO，不返回仍绑定 session 的 ORM 对象。

- [ ] **Step 5: 实现确定性风险服务**

  提供：

  ```python
  async def inspect_farm(
      snapshot: FarmSnapshot,
      *,
      weather_provider: WeatherProvider,
  ) -> FarmInspectionResult:
      """用确定性规则生成风险和证据，LLM 不参与阈值判定。"""
  ```

  `WeatherProvider` 使用 `Protocol` 声明，生产适配器调用现有 `weather_service.get_forecast_with_alerts(location, days=2)`。将现有 `app/tools/weather_risk.py` 的阈值函数复用为纯函数，不复制第二套阈值。天气异常转换为数据缺口并记录 warning；数据库和所有权异常继续抛出。

- [ ] **Step 6: 验证并提交**

  Run: `pytest tests/services/test_farm_snapshot_service.py tests/services/test_farm_risk_service.py -q`

  Expected: PASS。

  Commit: `git add app/services/farm_snapshot_service.py app/services/farm_risk_service.py tests/services/test_farm_snapshot_service.py tests/services/test_farm_risk_service.py && git commit -m "feat: add farm snapshot and risk inspection"`

---

## Task 4: 实现提案幂等和人工审批边界

**Files:**

- Create: `app/services/farm_proposal_service.py`
- Test: `tests/services/test_farm_proposal_service.py`

- [ ] **Step 1: 写创建、越权、重复和审批测试**

  覆盖：

  - `create_pending_proposal()` 只写 `pending`；
  - 相同 `run_id + risk_fingerprint` 重试返回同一 `proposal_id`；
  - 高置信度提案必须至少有一条 `measured` 或 `rule` 证据；
  - `approve()` 从用户提交的 actions 生成任务；
  - 重复批准返回原任务，不重复插入；
  - 已拒绝提案不能批准，返回 409 `INVALID_PROPOSAL_TRANSITION`；
  - 非农场所有者返回 403。

- [ ] **Step 2: 运行失败测试**

  Run: `pytest tests/services/test_farm_proposal_service.py -q`

  Expected: FAIL，服务不存在。

- [ ] **Step 3: 实现事务化提案服务**

  固定接口为 `create_pending_proposal(*, user_id: int, farm_id: int, run_id: str, draft: ProposalDraft) -> FarmActionProposal`、`list_proposals(*, user_id: int, farm_id: int | None, status: ProposalStatus | None) -> list[FarmActionProposal]`、`approve(*, user_id: int, proposal_id: str, request: ProposalApprovalRequest) -> tuple[FarmActionProposal, list[FarmTask]]` 和 `reject(*, user_id: int, proposal_id: str, request: ProposalRejectRequest) -> FarmActionProposal`。

  实现规则：

  - `risk_fingerprint = sha256(f"{farm_id}:{draft.risk_key}".encode()).hexdigest()`；
  - 用 unique constraint 作为最终幂等保障，捕获 `IntegrityError` 后 rollback 并查询已有记录；
  - 审批在一个 session/事务内更新提案并逐条创建任务；
  - task 的 `action_key` 来自审批 actions，unique constraint 防止部分重试；
  - 非法状态转换使用 `AppException(status_code=409, code="INVALID_PROPOSAL_TRANSITION", message="当前提案状态不允许该操作")`。

- [ ] **Step 4: 验证并提交**

  Run: `pytest tests/services/test_farm_proposal_service.py -q`

  Expected: PASS。

  Commit: `git add app/services/farm_proposal_service.py tests/services/test_farm_proposal_service.py && git commit -m "feat: add idempotent farm proposals"`

---

## Task 5: 实现任务状态机、执行证据和复核草稿

**Files:**

- Create: `app/services/farm_task_service.py`
- Test: `tests/services/test_farm_task_service.py`

- [ ] **Step 1: 写状态转换表的参数化失败测试**

  合法转换固定为：

  ```python
  ALLOWED_TRANSITIONS = {
      "pending": {"in_progress", "cancelled"},
      "in_progress": {"submitted", "cancelled"},
      "submitted": {"completed", "returned"},
      "returned": {"in_progress", "cancelled"},
      "completed": set(),
      "cancelled": set(),
  }
  ```

  参数化断言所有合法边通过，所有其他边返回 409 `INVALID_TASK_TRANSITION`。另外覆盖：

  - `submit()` 至少要求 note、轨迹或附件三者之一；
  - 关联 trajectory 必须属于任务农场；
  - `save_verification_draft()` 仅允许 submitted 状态，只更新 verdict 不改 status；
  - `complete()` 只允许已有 `pass` 或 `manual_review` 复核草稿；
  - `return_task()` 记录退回原因；
  - 非所有者返回 403。

- [ ] **Step 2: 运行失败测试**

  Run: `pytest tests/services/test_farm_task_service.py -q`

  Expected: FAIL，服务不存在。

- [ ] **Step 3: 实现服务接口**

  提供以下固定接口：

  - `list_tasks(*, user_id: int, farm_id: int | None, status: TaskStatus | None) -> list[FarmTask]`
  - `start(*, user_id: int, task_id: str) -> FarmTask`
  - `submit(*, user_id: int, task_id: str, request: TaskSubmitRequest) -> FarmTask`
  - `get_task_evidence(*, user_id: int, task_id: str) -> TaskEvidenceBundle`
  - `save_verification_draft(*, user_id: int, task_id: str, verdict: TaskVerificationDraft) -> FarmTask`
  - `complete(*, user_id: int, task_id: str, note: str) -> FarmTask`
  - `return_task(*, user_id: int, task_id: str, note: str) -> FarmTask`

  把通用的所有权查询和 `_transition()` 保持为私有函数；每次转换在一个事务内更新 `updated_at` 和 execution 审计数组，审计项包含 actor=`human`、action、note、timestamp。

- [ ] **Step 4: 验证并提交**

  Run: `pytest tests/services/test_farm_task_service.py -q`

  Expected: PASS。

  Commit: `git add app/services/farm_task_service.py tests/services/test_farm_task_service.py && git commit -m "feat: add farm task state machine"`

---

## Task 6: 将农场能力暴露为受控 Agent 工具

**Files:**

- Create: `app/tools/farm_agent_tools.py`
- Modify: `app/tools/meta.py: SideEffect and TOOL_META`
- Modify: `app/tools/mcp_loader.py: get_local_tools`
- Test: `tests/tools/test_farm_agent_tools.py`
- Test: `tests/tools/test_tool_meta.py`

- [ ] **Step 1: 写上下文注入和工具权限失败测试**

  测试直接调用工具的 coroutine/sync function，断言：

  - 缺失 `FarmRunContext` 时失败；
  - 工具签名中没有 `user_id` 和 `farm_id`；
  - 上下文用户只能读取自己的农场；
  - `create_action_proposal` 强制使用 context.run_id；
  - `save_task_verification_draft` 强制使用 context.task_id；
  - 本地工具集合包含七个新工具且无重名。

- [ ] **Step 2: 写 ToolMeta 失败测试**

  固定元数据：

  | Tool | read_only | concurrency_safe | side_effect | risk_level |
  |---|---:|---:|---|---|
  | `get_farm_snapshot` | true | true | none | low |
  | `inspect_farm_weather_risks` | true | true | network | medium |
  | `get_field_work_quality` | true | true | none | low |
  | `get_pending_farm_tasks` | true | true | none | low |
  | `get_task_evidence` | true | true | none | low |
  | `create_action_proposal` | false | false | database | medium |
  | `save_task_verification_draft` | false | false | database | medium |

- [ ] **Step 3: 运行失败测试**

  Run: `pytest tests/tools/test_farm_agent_tools.py tests/tools/test_tool_meta.py -q`

  Expected: FAIL，新工具或 `database` SideEffect 不存在。

- [ ] **Step 4: 实现薄工具适配器**

  在 `farm_agent_tools.py` 使用 `@tool` 定义上述七个工具。每个工具第一行调用 `require_farm_run_context()`，随后只调用 Task 3–5 的服务；不直接创建 session，不接受身份字段。工具返回 `model_dump(mode="json")` 后的 dict。

  `inspect_farm_weather_risks` 可接受 `days: int = 2`，限制 `ge=1, le=7`；其他读取工具只接受业务筛选参数，如 `field_id`、`limit`。

- [ ] **Step 5: 注册安全元数据和本地工具**

  把 `SideEffect` 扩展为 `Literal["none", "external", "filesystem", "network", "database"]`，同步说明文字。将七个 ToolMeta 加入中央注册表，并在 `get_local_tools()` 静态导入和返回它们。

- [ ] **Step 6: 验证并提交**

  Run: `pytest tests/tools/test_farm_agent_tools.py tests/tools/test_tool_meta.py -q`

  Expected: PASS 且 `warn_unregistered_tools()` 不报告新增工具。

  Commit: `git add app/tools/farm_agent_tools.py app/tools/meta.py app/tools/mcp_loader.py tests/tools/test_farm_agent_tools.py tests/tools/test_tool_meta.py && git commit -m "feat: expose controlled farm agent tools"`

---

## Task 7: 农业化 Skill、二级 Agent 和 fallback

**Files:**

- Create: `app/skills/definitions/farm_inspection/SKILL.md`
- Create: `app/skills/definitions/farm_task_verification/SKILL.md`
- Modify: `app/skills/registry.py: GENERIC_SKILL_NAME and get_or_generic`
- Modify: `app/agents/subagents/__init__.py`
- Modify: `app/agents/subagents/runner.py`
- Modify: `app/runtime/agent_harness.py`
- Modify: `app/runtime/tool_filter.py`
- Modify: `app/agents/skill_router.py`
- Modify: `app/agents/replanner.py`
- Modify: `app/skills/README.md`
- Modify: `docs/skill_development_guide.md`
- Delete: `app/skills/definitions/generic_oncall/SKILL.md`
- Test: `tests/skills/test_farm_agent_skills.py`
- Test: `tests/agents/test_agriculture_prompts.py`

- [ ] **Step 1: 写 Skill 注册和白名单失败测试**

  断言：

  ```python
  assert registry.GENERIC_SKILL_NAME == "agriculture_qa"
  assert registry.get_or_generic("missing").name == "agriculture_qa"
  assert registry.get("farm_inspection").allowed_tools == {
      "get_farm_snapshot",
      "inspect_farm_weather_risks",
      "get_field_work_quality",
      "get_pending_farm_tasks",
      "search_knowledge_base",
      "create_action_proposal",
  }
  assert registry.get("farm_task_verification").allowed_tools == {
      "get_task_evidence",
      "get_field_work_quality",
      "search_knowledge_base",
      "save_task_verification_draft",
  }
  ```

  同时断言 definitions 下不存在 `generic_oncall`。

- [ ] **Step 2: 写提示词遗留词扫描测试**

  扫描实际运行文件，禁止以下不区分大小写模式：`AIOps`、`SRE`、`server root cause`、`generic_oncall`、`故障诊断报告`。扫描范围只包含运行代码和 Skill，不包含历史迁移、设计/计划文档和兼容历史来源说明。

- [ ] **Step 3: 运行失败测试**

  Run: `pytest tests/skills/test_farm_agent_skills.py tests/agents/test_agriculture_prompts.py -q`

  Expected: FAIL，Farm Skill 不存在且存在遗留词。

- [ ] **Step 4: 创建两个严格 playbook**

  `farm_inspection/SKILL.md` frontmatter：

  ```yaml
  ---
  name: farm_inspection
  triggers:
    - 农场巡检
    - 综合巡检
    - 暴雨风险
  allowed_tools:
    - get_farm_snapshot
    - inspect_farm_weather_risks
    - get_field_work_quality
    - get_pending_farm_tasks
    - search_knowledge_base
    - create_action_proposal
  risk_level: medium
  context: inline
  ---
  ```

  正文规定证据顺序、事实/规则/推断区分、无证据不产生高置信度提案、最后必须输出结构化提案和人工确认提示。

  `farm_task_verification/SKILL.md` 使用上述四个工具，规定 verdict 枚举，明确“保存草稿不改变任务状态”。

- [ ] **Step 5: 替换二级 Agent 和通用 fallback**

  将旧二级 Agent 改为：

  - `farm_data_analyst`：只收集农场、地块、轨迹和任务事实；
  - `agronomy_researcher`：天气、知识库、作物阶段和不确定性；
  - `farm_work_planner`：行动、截止时间和验收条件，不做最终审批。

  同步 delegate 工具名称和 ToolMeta；将 harness、router、replanner、tool filter 中的 fallback 改为 `agriculture_qa`，最终报告标题固定为“农业风险分析报告”。

- [ ] **Step 6: 删除 generic_oncall 并更新文档**

  删除旧 Skill 文件；文档只描述农业 fallback 和两种 Farm Skill，不再把 `generic_oncall` 作为可用技能。

- [ ] **Step 7: 验证并提交**

  Run: `pytest tests/skills/test_farm_agent_skills.py tests/agents/test_agriculture_prompts.py -q`

  Expected: PASS。

  Commit: `git add app/skills app/agents/subagents app/runtime/agent_harness.py app/runtime/tool_filter.py app/agents/skill_router.py app/agents/replanner.py docs/skill_development_guide.md tests/skills/test_farm_agent_skills.py tests/agents/test_agriculture_prompts.py && git commit -m "refactor: replace legacy ops skills with farm workflows"`

---

## Task 8: 直接将 AIOps Graph 与 Service 改写为 Farm Agent

**Files:**

- Create: `app/services/farm_agent_service.py`
- Modify: `app/agents/state.py: PlanExecuteState`
- Modify: `app/agents/graph.py: build_aiops_graph`
- Modify: `app/agents/__init__.py`
- Modify: `app/agents/fork_runner.py`
- Modify: `app/agents/stream_sink.py`
- Modify: `app/runtime/tool_runner.py`
- Delete: `app/services/aiops_service.py`
- Test: `tests/agents/test_farm_agent_graph.py`
- Test: `tests/services/test_farm_agent_service.py`

- [ ] **Step 1: 写图命名、状态注入和 SSE 失败测试**

  断言：

  - `app.agents.build_farm_agent_graph` 可导入，`build_aiops_graph` 不可导入；
  - 初始 state 包含 `user_id/farm_id/run_id/run_type/business_context/proposal_ids`；
  - inspection 强制首选 `farm_inspection`，verification 强制首选 `farm_task_verification`；
  - SSE 至少按顺序出现 `start → context_loaded → skill_selected → plan → report → complete`；
  - 工具事件包含 tool name、status、duration，不包含敏感 prompt 或 API key；
  - 成功、图异常、工具异常、客户端取消都关闭 sink 并落 AgentRun；
  - 新历史记录 `source == "farm_agent"`。

- [ ] **Step 2: 运行失败测试**

  Run: `pytest tests/agents/test_farm_agent_graph.py tests/services/test_farm_agent_service.py -q`

  Expected: FAIL，Farm Agent graph/service 不存在。

- [ ] **Step 3: 扩展状态并重命名 graph builder**

  在 `PlanExecuteState` 增加：

  ```python
  user_id: int
  farm_id: int
  run_id: str
  run_type: Literal["inspection", "task_verification"]
  business_context: dict[str, Any]
  proposal_ids: Annotated[list[str], operator.add]
  ```

  将 `build_aiops_graph()` 重命名为 `build_farm_agent_graph()`，同步 `agents/__init__.py` 与 `fork_runner.py`，不保留旧别名。图节点算法保持不变，只将初始 Skill 和农业报告语义接入。

- [ ] **Step 4: 从旧服务迁移可靠运行能力**

  `farm_agent_service.py` 提供 `stream_inspection(*, user_id: int, request: FarmInspectionRequest) -> AsyncIterator[dict[str, Any]]` 和 `stream_task_verification(*, user_id: int, task_id: str) -> AsyncIterator[dict[str, Any]]` 两个入口。

  复用旧服务的 graph 执行与取消、stream sink 合并、并发限制、预算事件、transition history、token/tool/duration 统计和 AgentRun 持久化。新增流程：

  1. 服务入口先校验 farm/task 所有权；
  2. 生成 UUID run_id 并绑定 `FarmRunContext`；
  3. inspection 在图前生成结构化 snapshot 和风险摘要，写入 `business_context`；
  4. verification 将 task evidence 写入 `business_context`；
  5. AgentRun 开始即写 `user_id/farm_id/run_type/context_snapshot_json`；
  6. 最终写 `outcome_json`，包含 proposal_ids 或 task verdict；
  7. history 新记录使用 `source=farm_agent`；
  8. `asyncio.CancelledError` 单独处理，状态写 `cancelled` 后重新抛出。

- [ ] **Step 5: 删除旧 Service 和遗留命名**

  更新所有内部引用后删除 `app/services/aiops_service.py`。把 stream sink/tool runner 的运行日志和注释改成 Farm Agent 语义，但不改变公共运行行为。

- [ ] **Step 6: 验证并提交**

  Run: `pytest tests/agents/test_farm_agent_graph.py tests/services/test_farm_agent_service.py -q`

  Run: `rg -n "aiops_service|build_aiops_graph" app tests`

  Expected: tests PASS；`rg` 无结果。

  Commit: `git add app/agents app/runtime/tool_runner.py app/services tests/agents/test_farm_agent_graph.py tests/services/test_farm_agent_service.py && git commit -m "refactor: convert aiops runtime to farm agent"`

---

## Task 9: 替换 API、接通提案/任务接口并保留历史可读性

**Files:**

- Create: `app/api/v1/farm_agent.py`
- Create: `app/api/v1/farm_tasks.py`
- Modify: `app/main.py: router imports and include_router calls`
- Modify: `app/api/v1/history.py`
- Modify: `app/api/v1/webhook.py`
- Delete: `app/api/v1/aiops.py`
- Delete: `app/schemas/aiops.py`
- Test: `tests/api/test_farm_agent_api.py`
- Test: `tests/api/test_farm_tasks_api.py`
- Test: `tests/api/test_legacy_aiops_removal.py`

- [ ] **Step 1: 写认证、所有权和旧路由失败测试**

  使用 FastAPI dependency override 和 mock service，覆盖：

  - 未认证 inspection 返回 401；
  - 自有 farm 返回 SSE，跨用户 farm 返回 403；
  - `/api/v1/aiops/diagnose` 和 `/api/v1/aiops/timeline/x` 返回 404；
  - timeline 只能读取当前用户的 AgentRun；
  - proposal approve/reject、task start/submit/complete/return 都要求认证；
  - 重复 approve 返回相同 task IDs；
  - verify stream 只保存草稿，task 仍为 submitted；
  - history source 过滤同时接受 `aiops` 与 `farm_agent`。

- [ ] **Step 2: 运行失败测试**

  Run: `pytest tests/api/test_farm_agent_api.py tests/api/test_farm_tasks_api.py tests/api/test_legacy_aiops_removal.py -q`

  Expected: FAIL，新路由不存在，旧路由仍存在。

- [ ] **Step 3: 实现 Farm Agent 路由**

  `app/api/v1/farm_agent.py` 使用 prefix `/farm-agent`、tag `farm-agent`，提供：

  ```text
  POST /inspections/stream
  GET  /runs/{run_id}/timeline
  GET  /proposals
  POST /proposals/{proposal_id}/approve
  POST /proposals/{proposal_id}/reject
  ```

  所有路由注入 `current_user = Depends(get_current_user)`。SSE generator 捕获普通异常并产出结构化 error；保留 `CancelledError` 传播给 service。timeline 从真实 AgentRun transitions、统计和 outcome 组装，不生成模拟节点。

- [ ] **Step 4: 实现任务路由**

  `app/api/v1/farm_tasks.py` 使用 prefix `/farm-tasks`，提供：

  ```text
  GET  /
  POST /{task_id}/start
  POST /{task_id}/submit
  POST /{task_id}/verify/stream
  POST /{task_id}/complete
  POST /{task_id}/return
  ```

  普通响应统一 `ApiResponse[T]`；所有业务状态错误交给 service 的 `AppException`，router 不自行重写状态机。

- [ ] **Step 5: 更新 main、history 和 webhook**

  - `app/main.py` 删除 aiops import/include，加入 farm_agent 和 farm_tasks；
  - history 文档说明 `aiops` 是只读历史来源，列表查询不改写旧记录；
  - webhook 只有在现有签名校验通过、payload 含合法 `farm_id` 且能确定 owner 时调用 `stream_inspection()`；否则只记录 warning 并返回 accepted，不猜测用户或农场。

- [ ] **Step 6: 删除旧 Router 和 Schema**

  所有引用迁移后删除 `app/api/v1/aiops.py`、`app/schemas/aiops.py`。

- [ ] **Step 7: 验证并提交**

  Run: `pytest tests/api/test_farm_agent_api.py tests/api/test_farm_tasks_api.py tests/api/test_legacy_aiops_removal.py -q`

  Run: `rg -n "app\.schemas\.aiops|api\.v1 import aiops|/aiops/" app tests`

  Expected: tests PASS；除显式 404 回归测试字符串外无运行时引用。

  Commit: `git add app/api app/main.py app/schemas app/services/history_service.py tests/api && git commit -m "feat: expose farm agent workflow APIs"`

---

## Task 10: 增加可复现且显式标识的比赛演示场景

**Files:**

- Create: `app/data/demo_rainstorm_scenario.json`
- Create: `scripts/seed_competition_demo.py`
- Modify: `app/config.py: Settings`
- Modify: `.env.example`
- Test: `tests/services/test_competition_demo_seed.py`

- [ ] **Step 1: 写 fixture 完整性和 seed 幂等失败测试**

  fixture 必须包含：阳光农场、A1/A2/A3 三个地块、A1 水稻分蘖期、未来 24 小时 82mm 降雨、一条低质量轨迹输入。测试连续执行 seed 两次，断言农场、地块和轨迹数量不增加，且只修改指定演示用户的数据。

- [ ] **Step 2: 运行失败测试**

  Run: `pytest tests/services/test_competition_demo_seed.py -q`

  Expected: FAIL，fixture/script 不存在。

- [ ] **Step 3: 实现版本化 fixture 和幂等 seed**

  JSON 顶层固定为：

  ```json
  {
    "scenario_id": "rainstorm-v1",
    "label": "比赛演示数据",
    "farm": {"external_key": "demo-sunshine-farm", "name": "阳光农场"},
    "weather": {"rainfall_24h_mm": 82.0, "observed_at": "2026-07-18T08:00:00+08:00"},
    "fields": [],
    "trajectory_summaries": []
  }
  ```

  实际文件填入三个完整 fields 和一条 trajectory summary，不预写 Agent 计划、报告、提案或 verdict。脚本接受 `--username`，查找已有用户并以稳定 external key/名称幂等更新；找不到用户时明确退出非零，不创建默认密码。

  `Settings` 增加 `competition_demo_enabled: bool = False`，`.env.example` 记录默认关闭。真实模式不得自动读取 demo weather；只有请求明确传 `demo_scenario=rainstorm` 且配置开启时使用。

- [ ] **Step 4: 验证并提交**

  Run: `pytest tests/services/test_competition_demo_seed.py -q`

  Run: `python scripts/seed_competition_demo.py --help`

  Expected: PASS；帮助信息可见且不连接外部服务。

  Commit: `git add app/data/demo_rainstorm_scenario.json scripts/seed_competition_demo.py app/config.py .env.example tests/services/test_competition_demo_seed.py && git commit -m "feat: add reproducible competition demo scenario"`

---

## Task 11: 建立前端类型、API 和 SSE 状态层

**Files:**

- Create: `frontend-react/src/types/farmAgent.ts`
- Create: `frontend-react/src/api/farmAgent.ts`
- Create: `frontend-react/src/api/farmTasks.ts`
- Create: `frontend-react/src/stores/farmAgent.ts`
- Modify: `frontend-react/src/api/client.ts` only if SSE abort signal is not currently supported

- [ ] **Step 1: 定义与后端一一对应的 TypeScript 类型**

  包含 `FarmEvidence`、`FarmRisk`、`ProposedAction`、`FarmActionProposal`、`FarmTask`、`FarmAgentEvent`、`AgentRunTimeline`。所有 status/type 使用 string union，不用宽泛 `string`；时间字段统一 `string | null`；JSON payload 使用 `Record<string, unknown>`，不用 `any`。

- [ ] **Step 2: 实现 API 模块**

  `farmAgent.ts` 提供：

  ```typescript
  export function streamFarmInspection(
    request: FarmInspectionRequest,
    signal?: AbortSignal,
  ): AsyncGenerator<FarmAgentEvent>

  export function getFarmRunTimeline(runId: string): Promise<AgentRunTimeline>
  export function listFarmProposals(filters: ProposalFilters): Promise<FarmActionProposal[]>
  export function approveFarmProposal(proposalId: string, body: ProposalApprovalRequest): Promise<ApprovalResult>
  export function rejectFarmProposal(proposalId: string, decisionNote: string): Promise<FarmActionProposal>
  ```

  `farmTasks.ts` 提供 list/start/submit/streamVerification/complete/return。复用 `authFetch`、`authFetchRaw` 和 `consumeSSE`；若当前 `consumeSSE` 不支持 signal，只做最小签名扩展并将 signal 传入 fetch。

- [ ] **Step 3: 实现独立 Farm Agent store**

  state 固定包含：`runStatus`、`activeRunId`、`events`、`risks`、`proposalIds`、`report`、`error`。actions：`startRun`、`appendEvent`、`finishRun`、`failRun`、`reset`。每次新巡检先清理旧事件；`appendEvent` 以 `event_id` 去重；store 不保存服务端 proposals/tasks 全量列表，那些由 React Query 管理。

- [ ] **Step 4: 前端静态验证并提交**

  Run: `npm run lint` in `frontend-react/`

  Run: `npm run build` in `frontend-react/`

  Expected: PASS。

  Commit: `git add frontend-react/src/types/farmAgent.ts frontend-react/src/api/farmAgent.ts frontend-react/src/api/farmTasks.ts frontend-react/src/stores/farmAgent.ts frontend-react/src/api/client.ts && git commit -m "feat: add farm agent frontend data layer"`

---

## Task 12: 实现 AI 农场驾驶舱和人工决策交互

**Files:**

- Create: `frontend-react/src/pages/FarmAgent.tsx`
- Create: `frontend-react/src/components/farm-agent/AgentRunTimeline.tsx`
- Create: `frontend-react/src/components/farm-agent/FarmRiskCard.tsx`
- Create: `frontend-react/src/components/farm-agent/ActionProposalCard.tsx`
- Create: `frontend-react/src/components/farm-agent/HumanApprovalBar.tsx`
- Create: `frontend-react/src/components/farm-agent/FarmTaskBoard.tsx`
- Create: `frontend-react/src/components/farm-agent/TaskVerificationCard.tsx`

- [ ] **Step 1: 实现驾驶舱页面骨架和巡检流**

  页面布局：顶部 farm selector + demo badge + 主巡检按钮；桌面端三列（农场/风险、Agent 时间线、待确认提案），底部任务看板；窄屏按上述顺序单列。farm 列表为空时显示“先创建农场”入口，不启动空巡检。

  页面通过 `AbortController` 管理运行；重复点击时禁用按钮；卸载时 abort；SSE `proposal_created` 到达后 invalidate proposal query；complete 后刷新 timeline/tasks。

- [ ] **Step 2: 实现证据和时间线组件**

  - `AgentRunTimeline` 显示 Skill、plan、tool call、step、replan、report、error，运行态有清晰当前节点；
  - `FarmRiskCard` 明确标注 evidence 的 `measured/rule/inference`，降级数据显示“数据缺口”；
  - 不展示模型 chain-of-thought，只展示结构化事件 message、工具名、状态和耗时。

- [ ] **Step 3: 实现提案人工审批**

  `ActionProposalCard` 展示 severity、confidence、evidence 和 actions。`HumanApprovalBar` 允许：

  - 勾选/取消动作；
  - 修改 assignee、due_at、instructions；
  - 输入 decision note；
  - approve 或 reject。

  mutation 期间按钮禁用；成功后刷新 proposals/tasks；409 显示“提案状态已变化，请刷新”，不重复创建任务。

- [ ] **Step 4: 实现任务看板和复核卡**

  `FarmTaskBoard` 按待执行、执行中、待复核、已完成/已取消分组。只显示当前状态允许的按钮。submit 表单至少要求文字、轨迹选择或附件 URL 之一。

  `TaskVerificationCard` 消费 verification SSE，展示 verdict、证据覆盖和缺口；只有人类按钮能调用 complete/return。AI 返回 pass 时也不自动完成。

- [ ] **Step 5: 前端验证并提交**

  Run: `npm run lint` in `frontend-react/`

  Run: `npm run build` in `frontend-react/`

  Expected: PASS，TypeScript 无 `any` 逃逸和未处理 promise。

  Commit: `git add frontend-react/src/pages/FarmAgent.tsx frontend-react/src/components/farm-agent && git commit -m "feat: build farm agent competition cockpit"`

---

## Task 13: 接入导航、工作台和农场入口

**Files:**

- Modify: `frontend-react/src/App.tsx`
- Modify: `frontend-react/src/components/layout/AppLayout.tsx`
- Modify: `frontend-react/src/pages/Dashboard.tsx`
- Modify: `frontend-react/src/pages/Farms.tsx`

- [ ] **Step 1: 注册唯一产品入口**

  在 `App.tsx` 增加受保护路由 `/workspace/farm-agent`。`AppLayout` 导航名称使用“AI 农场驾驶舱”，不使用“AIOps”或“智能问答”。

- [ ] **Step 2: 调整 Dashboard 信息层级**

  首屏新增：今日 AI 风险摘要、待确认提案数、进行中任务数、最近一次巡检状态和“开始 AI 综合巡检”主按钮。保留系统健康卡但降到次要区域；不要删除现有系统可观测能力。

- [ ] **Step 3: 给 Farms 页面增加最小入口**

  只在农场卡片/详情操作区增加“AI 巡检”链接，并携带 `farmId` query parameter；不重构现有大型 Farms 页面。

- [ ] **Step 4: 前端验证并提交**

  Run: `npm run lint` in `frontend-react/`

  Run: `npm run build` in `frontend-react/`

  Expected: PASS；直接访问、Dashboard 入口和 Farms 入口均能到达驾驶舱。

  Commit: `git add frontend-react/src/App.tsx frontend-react/src/components/layout/AppLayout.tsx frontend-react/src/pages/Dashboard.tsx frontend-react/src/pages/Farms.tsx && git commit -m "feat: integrate farm agent into workspace"`

---

## Task 14: 清理遗留语义、更新架构文档并完成闭环验收

**Files:**

- Modify: `docs/architecture.md`
- Modify: project README files that currently advertise AIOps routes
- Test: `tests/integration/test_farm_agent_closed_loop.py`
- Test: `tests/integration/test_runtime_legacy_scan.py`

- [ ] **Step 1: 写完整闭环集成测试**

  使用 mock LLM、mock weather provider 和测试数据库执行：

  ```text
  seed demo farm
  → stream inspection
  → receive structured proposal
  → approve selected actions
  → start task
  → submit trajectory/text evidence
  → stream verification
  → assert task still submitted
  → human complete
  → assert timeline and AgentRun outcome are readable
  ```

  断言未批准前没有 task，重复批准没有重复 task，AI verification 没有直接完成 task。

- [ ] **Step 2: 写运行时遗留扫描测试**

  对 `app/` 和 `frontend-react/src/` 断言不存在：

  - `aiops_service`
  - `build_aiops_graph`
  - `/api/v1/aiops`
  - `generic_oncall`
  - 用户可见的 `AIOps` / `SRE` 文案

  允许 `history` 的 source 枚举和迁移/兼容读取逻辑出现字符串 `aiops`。

- [ ] **Step 3: 更新架构与接口文档**

  `docs/architecture.md` 使用 Farm Agent 图、两个 Skill、七个工具、两个人工决策门和新 API。README 的启动命令保持不变，接口示例改为 `/api/v1/farm-agent/inspections/stream`。明确 demo 数据标识和真实模式差异。

- [ ] **Step 4: 运行专项后端测试**

  Run: `pytest tests/models tests/schemas tests/runtime tests/tools tests/skills tests/agents tests/services/test_farm_snapshot_service.py tests/services/test_farm_risk_service.py tests/services/test_farm_proposal_service.py tests/services/test_farm_task_service.py tests/services/test_farm_agent_service.py tests/api/test_farm_agent_api.py tests/api/test_farm_tasks_api.py tests/api/test_legacy_aiops_removal.py tests/integration -q`

  Expected: PASS。

- [ ] **Step 5: 运行全量验证**

  Run: `alembic upgrade head`

  Run: `pytest -q`

  Run: `npm run lint` in `frontend-react/`

  Run: `npm run build` in `frontend-react/`

  Run: `rg -n "aiops_service|build_aiops_graph|generic_oncall|/api/v1/aiops" app frontend-react/src`

  Expected: migrations、pytest、lint、build 全部 PASS；`rg` 仅允许 history 的显式历史来源兼容说明，不得出现运行入口或符号引用。

- [ ] **Step 6: 手工比赛演示验收**

  启动后按以下顺序检查：

  1. 加载带“比赛演示数据”标识的阳光农场；
  2. 启动综合巡检，时间线至少显示三类证据和一次工具调用；
  3. 确认 82mm 暴雨触发确定性风险；
  4. 查看证据来源、置信度和数据缺口；
  5. 删除一项 action 后批准，其余 action 各生成一个任务；
  6. 启动并提交任务证据；
  7. AI 给出复核草稿，但任务仍处于 submitted；
  8. 人工完成或退回后状态正确；
  9. 刷新页面后 proposal、task、timeline 和 report 仍可恢复；
  10. 断网或 mock weather 失败时页面显示降级巡检，不伪造天气证据。

- [ ] **Step 7: 最终提交**

  Commit: `git add docs tests/integration && git commit -m "test: verify farm agent competition workflow"`

---

## Spec Coverage Review

- AI 价值：巡检、证据、计划、提案、任务、复核形成一个可见闭环，而非增强 Chat。
- 权限边界：当前仍是平台 `admin/user`；所有业务副作用由农场 owner 的已认证账户执行，assignee 只作显示字段。
- Agent 安全：`FarmRunContext` 注入身份，工具不接收 user_id；只能写 pending proposal 和 verification draft。
- 直接改写：旧 AIOps router/service/schema/builder 与 generic fallback 全部删除，不保留运行时别名。
- 历史兼容：旧 `source=aiops` 记录继续可查，新数据只写 `farm_agent`。
- 比赛稳定性：演示 fixture 版本化、显式标识、可幂等 seed，不硬编码 Agent 输出。
- 可观测性：真实 transitions、tool calls、token、耗时、proposal IDs 和 verdict 持久化到 AgentRun。
- 人工门控：提案批准和任务完成是两道普通 API 决策门；AI 永远不跨过最终状态。
- 降级：天气、知识库和 SSE 异常均有结构化结尾与数据缺口，不把失败描述成成功。
- 验证：每层都有失败测试和专项命令，最终包含迁移、全量 pytest、前端 lint/build 和手工比赛演示。

## Implementation Order Checkpoints

1. Tasks 1–5 完成后，领域闭环和权限规则已能在纯服务层验证。
2. Tasks 6–9 完成后，旧 AIOps 链已被 Farm Agent 完整替换，后端 API 可独立演示。
3. Tasks 10–13 完成后，比赛数据和驾驶舱可用。
4. Task 14 只做遗留清理、文档和全链验收；若此时发现功能缺口，回到对应任务修复并补回归测试，不在验收任务里堆补丁。
