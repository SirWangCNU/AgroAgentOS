# Mandatory Development Standards Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish a mandatory, shared development standard for human contributors and AI coding assistants, with `AGENTS.md` as the enforcement entry point and `docs/DEVELOPMENT_STANDARDS.md` as the single detailed source of truth.

**Architecture:** The implementation has two documentation units with separate responsibilities. `docs/DEVELOPMENT_STANDARDS.md` owns all detailed rules, checklists, exception handling, and verification matrices; `AGENTS.md` owns only the mandatory AI workflow summary and a link to the detailed standard. This avoids duplicated rules while ensuring every repository-aware AI sees the gate before editing code.

**Tech Stack:** Markdown, Git, PowerShell validation commands, existing AgroAgentOS repository conventions.

## Global Constraints

- Do not modify business code, configuration, dependencies, tests, or the user's existing uncommitted changes.
- Detailed rules must exist only in `docs/DEVELOPMENT_STANDARDS.md`; `AGENTS.md` contains a mandatory summary and link.
- Use the normative terms “必须”, “禁止”, “应当”, and “可以” with the meanings approved in the design.
- AI may not self-approve exceptions to a “必须” or “禁止” rule.
- Do not add CI, pre-commit, Python formatters, linters, or other automation in this implementation.
- All Markdown paths and commands must match the repository as it exists on 2026-07-15.
- Stage and commit only the files named by each task; never use `git add .` or `git add -A`.
- Treat `docs/superpowers/specs/2026-07-15-development-standards-design.md` as the approved requirements source.

## File Structure

- Create `docs/DEVELOPMENT_STANDARDS.md`: the complete, human-readable and AI-readable source of truth for mandatory engineering rules.
- Modify `AGENTS.md`: add the short mandatory AI execution protocol near the top, before command and architecture reference material.
- Read `docs/superpowers/specs/2026-07-15-development-standards-design.md`: confirm every approved requirement is represented; do not modify this approved design during implementation.

---

### Task 1: Create the complete development standard

**Files:**
- Create: `docs/DEVELOPMENT_STANDARDS.md`
- Read: `docs/superpowers/specs/2026-07-15-development-standards-design.md`
- Reference: `AGENTS.md`

**Interfaces:**
- Consumes: the approved rule hierarchy, technical boundaries, verification matrix, exception model, and acceptance criteria from the design document.
- Produces: one canonical Markdown document at `docs/DEVELOPMENT_STANDARDS.md` that later tasks can link to as the detailed source of truth.

- [ ] **Step 1: Record the pre-change workspace state**

Run:

```powershell
git status --short
```

Expected: the existing mini-program, authentication, profile, and launcher changes may be present; `docs/DEVELOPMENT_STANDARDS.md` must not yet appear. Preserve the output for comparison after the task.

- [ ] **Step 2: Create the document header and normative language**

Create `docs/DEVELOPMENT_STANDARDS.md` with this opening structure and meaning:

```markdown
# AgroAgentOS 开发规范

> 本规范同时约束人类开发者与 AI 开发助手。“必须”和“禁止”属于交付门禁；不满足适用门禁时，不得声称任务已完成、已修复或可交付。

## 1. 适用范围与规则等级

- **必须**：交付门禁，不满足时不得交付。
- **禁止**：任何任务中都不能默认执行的行为。
- **应当**：默认执行；偏离时必须说明具体理由。
- **可以**：在符合任务范围和现有架构的前提下选择执行。

规则优先级：用户当前明确要求 > 根目录 `AGENTS.md` > 本规范 > 目标模块局部惯例。发生冲突时必须说明冲突；不得把一般性指令解释为泄露凭证、破坏用户未提交改动或执行范围外破坏性操作的授权。
```

The opening must also state that new code follows the standard immediately, while directly related legacy violations are improved only within the current task scope.

- [ ] **Step 3: Add the mandatory three-stage workflow and checklists**

Add sections named exactly:

```markdown
## 2. 强制开发流程
### 2.1 编码前门禁
### 2.2 编码中门禁
### 2.3 交付前门禁
```

The encoding-before checklist must require reading repository instructions, checking `git status`, examining adjacent implementation/tests/schemas/config/docs, defining scope and compatibility risks, and choosing validation commands before editing.

The encoding-during checklist must require minimal focused changes, preservation of user edits, compliance with existing boundaries, explicit handling of errors, and impact assessment before dependency/API/schema/auth changes. It must prohibit unrelated refactors and test manipulation.

The delivery checklist must require implementation completeness, applicable verification, documentation synchronization, sensitive-data review, diff review, and a final report containing changed behavior, key design, files, verification results, skipped verification with reasons, and remaining risks.

- [ ] **Step 4: Add shared engineering, error, security, and compatibility rules**

Add focused sections covering:

```markdown
## 3. 通用工程规则
## 4. 错误处理、日志与可观测性
## 5. 配置、依赖与安全
## 6. API 与兼容性
```

Include enforceable rules for single responsibility, naming, comments that explain reasons rather than restate code, no silent exception swallowing, no sensitive log content, `Settings` plus `.env.example` synchronization, no real credentials, dependency justification, validation of files/URLs/commands, and explicit approval for breaking API or authentication changes.

- [ ] **Step 5: Add backend and database boundaries**

Add:

```markdown
## 7. Python 与 FastAPI
## 8. 数据库与 Alembic
```

State these exact project boundaries:

- `app/api/v1/` handles HTTP concerns, dependency injection, authorization, and response assembly only.
- Business logic belongs in `app/services/`; routers must not directly access the database.
- Infrastructure adapters belong in `app/core/` or an explicit tool adapter.
- Requests and responses use `app/schemas/`; APIs use `ApiResponse[T]` where the project contract requires it.
- Expected business failures use the `AppException` hierarchy and global handlers.
- Async request paths must not execute blocking I/O without an async client or explicit thread offload.
- ORM/schema changes require a new Alembic migration and an upgrade-path check.
- Database behavior must be reviewed for SQLite and MySQL compatibility.
- Structured text columns follow the existing `_json` property convention.
- Existing production migrations must not be rewritten to hide a new schema change.

- [ ] **Step 6: Add React, mini-program, and Agent/Skill boundaries**

Add:

```markdown
## 9. React 与 TypeScript
## 10. 微信小程序
## 11. Agent、Skill 与工具
```

React rules must assign reusable HTTP/SSE access to `frontend-react/src/api/`, server state to TanStack React Query, cross-page client state to Zustand, and shared types to the existing type structure. Prohibit unjustified `any`, double assertions used to bypass type safety, and duplicated authentication handling. Require loading, empty, error, and success states plus `npm run lint` and `npm run build` when applicable.

Mini-program rules must require reuse of `services/` and `utils/`, lifecycle-safe request handling, loading/empty/error/auth-expiry states, no duplicated public behavior, and no hard-coded backend addresses or secrets.

Agent rules must preserve `SkillRouter → Planner → Executor → Replanner`, tool execution through the existing runtime, failure memory and maximum-step behavior, Skill frontmatter and whitelist rules, explicit risk metadata, no default high-risk writes, and defensive structured parsing of LLM output.

- [ ] **Step 7: Add the verification matrix with exact repository commands**

Add a `## 12. 测试与验证门禁` section containing at least this matrix:

| 改动类型 | 必须执行的最低验证 |
| --- | --- |
| Python 单模块业务逻辑 | `pytest <相关测试文件> -q` |
| 后端跨模块、认证、Agent 核心链路 | 相关测试，然后运行 `pytest` |
| React/TypeScript | 在 `frontend-react/` 运行 `npm run lint` 和 `npm run build` |
| 微信小程序 | 检查受影响 JS/JSON/WXML/WXSS，并使用微信开发者工具或等价方式验证受影响流程；报告具体范围 |
| ORM/数据库结构 | 相关测试、`alembic upgrade head`，并审查 SQLite/MySQL 兼容性 |
| Skill/工具 | 验证注册加载、路由或白名单、成功路径和失败路径 |
| 配置/启动脚本 | 验证配置解析，并运行目标命令或等价 smoke test |
| 仅文档 | 检查链接、命令、路径、Markdown 和内容一致性 |

State that failures may only be resolved by fixing the cause, proving and reporting that a pre-existing failure is unrelated, or reporting a blocker. Explicitly prohibit deleting tests, weakening assertions, suppressing errors, or hiding failures.

- [ ] **Step 8: Add Git, exception, maintenance, and delivery rules**

Add:

```markdown
## 13. Git 与变更管理
## 14. 例外审批
## 15. 文档同步与规范维护
## 16. Definition of Done
```

Require single-purpose changes, conventional prefixes already used by the repository (`feat:`, `fix:`, `refactor:`, `test:`, `docs:`), exact-path staging, and preservation of unrelated changes. State that AI does not commit, push, or create a PR unless requested by the user or an explicit workflow.

The exception section must require the violated rule, objective reason, correctness/security/compatibility impact, alternative verification, and remaining risk. Only the user can approve a mandatory-rule exception.

The Definition of Done must require completed behavior, passed applicable checks, usable migrations, no secrets, no unrelated changes, synchronized docs, and a complete delivery report before completion language is allowed.

- [ ] **Step 9: Add a consolidated prohibition list**

Add a `## 17. 禁止事项速查` section that explicitly prohibits direct database access from routers, secrets in source or logs, silent exception swallowing, type-system bypasses, schema changes without migrations, hard-coded environment values, destructive handling of user changes, unrelated refactors, test weakening, hidden failures, unverified completion claims, and temporary weakening of this standard.

- [ ] **Step 10: Validate the complete document**

Run:

```powershell
rg -n "^## " docs/DEVELOPMENT_STANDARDS.md
rg -n "TBD|TODO|待定|稍后补充|implement later|fill in" docs/DEVELOPMENT_STANDARDS.md
git diff --check -- docs/DEVELOPMENT_STANDARDS.md
```

Expected:

- The first command lists all 17 top-level sections.
- The second command returns no matches and may exit with code 1 because no prohibited placeholder exists.
- `git diff --check` returns no whitespace errors.

- [ ] **Step 11: Commit only the complete standard**

Run:

```powershell
git add -- docs/DEVELOPMENT_STANDARDS.md
git diff --cached --name-only
git commit -m "docs: add mandatory development standards"
```

Expected: the staged-file list contains only `docs/DEVELOPMENT_STANDARDS.md`; the commit succeeds without including any pre-existing worktree change.

---

### Task 2: Add the AI enforcement entry point

**Files:**
- Modify: `AGENTS.md:1-5`
- Read: `docs/DEVELOPMENT_STANDARDS.md`
- Read: `docs/superpowers/specs/2026-07-15-development-standards-design.md`

**Interfaces:**
- Consumes: the canonical rule document created by Task 1 at `docs/DEVELOPMENT_STANDARDS.md`.
- Produces: a mandatory repository entry point that tells AI assistants when to read the canonical document, which gates cannot be skipped, and how to report delivery status.

- [ ] **Step 1: Recheck the workspace before editing**

Run:

```powershell
git status --short
git diff -- AGENTS.md
```

Expected: the user's unrelated modifications remain present; `AGENTS.md` has no unreviewed local change before this task.

- [ ] **Step 2: Insert the mandatory protocol before `## Commands`**

Insert the following block after the project description and before `## Commands`:

```markdown
## Mandatory Development Protocol

All human contributors and AI coding assistants **must** follow [`docs/DEVELOPMENT_STANDARDS.md`](docs/DEVELOPMENT_STANDARDS.md). The terms “必须” and “禁止” in that document are delivery gates, not recommendations.

For every code change, AI assistants must:

1. Before editing, read the complete standard, inspect `git status`, examine the affected implementation and adjacent tests/contracts, and identify the required validation commands.
2. During editing, preserve user changes, keep the diff minimal, respect repository layer boundaries, and avoid unrelated refactors or unapproved dependency/API/schema/auth changes.
3. Before claiming completion, run every applicable test, build, migration, or static check from the standard; review the final diff; and report changed files, verification results, skipped checks with reasons, and remaining risks.

AI assistants must not self-approve an exception, weaken or delete tests to obtain a pass, hide failures, commit secrets, bypass types or migrations, overwrite unrelated worktree changes, or claim completion without evidence. If a mandatory gate cannot be met, stop the completion claim and request explicit user approval for the documented exception.
```

Do not duplicate the full backend, frontend, mini-program, Agent, database, or verification matrices in `AGENTS.md`; the canonical details remain in the linked document.

- [ ] **Step 3: Validate link, placement, and non-duplication**

Run:

```powershell
Test-Path docs\DEVELOPMENT_STANDARDS.md
Select-String -Path AGENTS.md -Pattern "docs/DEVELOPMENT_STANDARDS.md","## Mandatory Development Protocol","## Commands"
git diff --check -- AGENTS.md docs/DEVELOPMENT_STANDARDS.md
```

Expected:

- `Test-Path` prints `True`.
- `Select-String` shows the link and mandatory-protocol heading before `## Commands`.
- `git diff --check` returns no whitespace errors.

- [ ] **Step 4: Audit the implementation against the approved design**

Run:

```powershell
rg -n "编码前门禁|编码中门禁|交付前门禁|Python 与 FastAPI|React 与 TypeScript|微信小程序|Agent、Skill 与工具|数据库与 Alembic|测试与验证门禁|例外审批|Definition of Done|禁止事项速查" docs/DEVELOPMENT_STANDARDS.md
rg -n "Mandatory Development Protocol|must not self-approve|claim completion without evidence" AGENTS.md
git status --short
```

Expected: every required section or enforcement phrase is found. `git status --short` shows only `AGENTS.md` as the current task change plus the user's previously existing unrelated changes; no business file is newly modified by this plan.

- [ ] **Step 5: Review the final documentation diff**

Run:

```powershell
git diff -- AGENTS.md
git show --stat --oneline HEAD
```

Expected: the `AGENTS.md` diff contains only the mandatory protocol insertion. The previous commit contains only `docs/DEVELOPMENT_STANDARDS.md`.

- [ ] **Step 6: Commit only the AI enforcement entry point**

Run:

```powershell
git add -- AGENTS.md
git diff --cached --name-only
git commit -m "docs: enforce development protocol for AI"
```

Expected: the staged-file list contains only `AGENTS.md`; the commit succeeds without including any existing user changes.

- [ ] **Step 7: Perform the final clean-scope verification**

Run:

```powershell
git show --name-only --format=oneline HEAD
git status --short
```

Expected: the latest commit contains only `AGENTS.md`. The working tree may remain dirty only because of the same user-owned files recorded before Task 1; the implementation introduced no uncommitted business-code change.
