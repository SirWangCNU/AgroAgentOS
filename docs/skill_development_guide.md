# Skill 开发指南

本文档说明如何为 AIOps Platform 新增一个诊断 Skill。

## 目录

1. [概述](#1-概述)
2. [Skill 文件结构](#2-skill-文件结构)
3. [Frontmatter 字段详解](#3-frontmatter-字段详解)
4. [Playbook 编写规范](#4-playbook-编写规范)
5. [可用工具清单](#5-可用工具清单)
6. [完整示例](#6-完整示例)
7. [注册与生效](#7-注册与生效)
8. [高级: 新增自定义工具](#8-高级新增自定义工具)
9. [调试与验证](#9-调试与验证)

---

## 1. 概述

### 什么是 Skill

Skill 是本平台的**诊断能力单元**。每个 Skill 封装了一个特定领域的故障排查方法论, 包含:

- **元数据** (frontmatter): 名称、描述、触发词、允许使用的工具
- **Playbook** (Markdown 正文): 结构化的排查步骤, 直接注入 Planner LLM 的 prompt

### 工作流程

```
用户输入 → Skill Router (LLM 选择 Skill) → Planner (读 Playbook 生成计划)
         → Executor (用 allowed_tools 执行) → Replanner (评估/调整)
         → 输出报告
```

### 约定

- Skill 定义文件必须放在 `app/skills/definitions/<skill_name>/SKILL.md`
- `skill_name` 必须是 **snake_case** (仅小写字母、数字、下划线)
- 启动时自动扫描, 无需手动注册
- 必须保留 `generic_oncall` 作为兜底 Skill

---

## 2. Skill 文件结构

```
app/skills/definitions/
├── generic_oncall/SKILL.md          # 通用兜底 (必须保留)
├── host_resource_diagnosis/SKILL.md # 主机资源诊断
├── network_diagnosis/SKILL.md       # 网络连通性诊断
├── container_diagnosis/SKILL.md     # 容器诊断
└── your_new_skill/
    └── SKILL.md                     # <-- 你的新 Skill
```

单个 SKILL.md 的格式:

```markdown
---
name: your_new_skill
display_name: 你的 Skill 名称
description: 一句话描述, 给 Router LLM 看
triggers:
  - 触发词1
  - 触发词2
allowed_tools:
  - search_knowledge_base
  - some_mcp_tool
risk_level: low
---

# 你的 Playbook 标题

## 适用场景
...

## 排查步骤
...
```

---

## 3. Frontmatter 字段详解

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `name` | string | **是** | - | 唯一标识, snake_case, 如 `mysql_diagnosis` |
| `display_name` | string | **是** | - | 人类可读名, 前端展示用 |
| `description` | string | **是** | - | 一句话场景描述, Router LLM 据此做路由判断 |
| `triggers` | list[str] | 否 | `[]` | 触发关键字, 作为 Router 的提示 (非硬匹配) |
| `allowed_tools` | list[str] | 否 | `[]` | 工具白名单, Executor 只能用列表中的工具 |
| `risk_level` | string | 否 | `"low"` | `low` / `medium` / `high` |
| `context` | string | 否 | `"inline"` | `inline` (主图执行) / `fork` (子图执行) |
| `fork_max_iters` | int | 否 | `4` | fork 模式下子图最大循环次数 |

### 字段说明

**name** — 全局唯一, 用于日志、前端高亮、路由匹配。如果重复, 后加载的会覆盖先加载的。

**description** — 这是 Router LLM 做路由判断的核心依据。写清楚"适用什么问题", 比堆关键词更重要。

**triggers** — 纯辅助提示, 不是硬匹配规则。Router 主要靠 LLM 理解 description, triggers 只是补充。建议覆盖用户可能使用的口语化表达 (如"我电脑卡"、"网站打不开")。

**allowed_tools** — 工具名必须与 `TOOL_META` 中注册的名称或 MCP 服务器暴露的工具名完全一致。注意:
- 只读工具 (`read_only=True`) 会自动包含, 不需要显式列出
- 但如果想让 LLM 知道某个工具"优先用", 列出来有引导作用
- 工具名不存在时不会报错, 只是该工具不会被暴露

**risk_level**:
- `low` — 纯查询操作, 无副作用 (查日志、查指标、查知识库)
- `medium` — 调用外部 API 但不修改状态 (联网搜索、发通知)
- `high` — 涉及写操作 (重启服务、删文件、改配置), Harness 会要求人工确认

**context**:
- `inline` — playbook 注入主对话, 在主图的 plan-execute-replan 循环中执行。适合短平快的诊断任务。
- `fork` — 起独立子图运行, 只回传最终报告给主线。适合长报告、联网深度研究等会污染主对话上下文的任务。

---

## 4. Playbook 编写规范

Playbook 是 SKILL.md 中 `---` 分隔线之后的 Markdown 正文, 会被原样注入 Planner LLM 的 prompt。写得好坏直接决定诊断质量。

### 结构建议

```markdown
# Skill 名称 Playbook

## 适用场景
- 场景 A: ...
- 场景 B: ...
- 场景 C: ...

**不适用**: 明确说明哪些问题不归这个 Skill 管 (避免 Router 误选)

## 数据来源约束 (可选但推荐)
- 工具数据来自哪里 (本机采集 / 远程监控 / 知识库)
- 哪些数据不能编造
- 知识库的使用方式 (参考 vs 证据)

## Phase 1: 快速定位 (必做)
1. 调 `tool_a` 获取初步信息
2. 根据结果判断走哪个分支

## Phase 2-A: 分支 A
1. 调 `tool_b` 做深入排查
2. 判断根因

## Phase 2-B: 分支 B
1. ...

## Phase N: 输出报告
**格式要求**: 明确告诉 LLM 报告应该包含哪些部分
- 现状快照 (具体数值)
- 问题判断
- 根因分析
- 止损建议
- 长期优化方向

## 注意事项
- 安全约束 (不要自主执行写操作)
- 数据约束 (不要编造工具未返回的内容)
- 边界条件 (什么情况下该承认"数据不足")
```

### 编写要点

1. **适用/不适用写清楚** — Router LLM 会读 description, 但 playbook 开头的适用场景帮助 Planner 更好理解边界
2. **分阶段, 每步指定工具** — LLM 擅长按步骤执行, 明确 "调 `tool_x` 看 `field_y`" 比泛泛说 "检查系统状态" 效果好得多
3. **分支逻辑** — 用 "如果 X 则走 Phase 2-A, 如果 Y 则走 Phase 2-B" 的形式, 让 LLM 做条件判断
4. **输出格式** — 明确报告结构, LLM 会严格遵循
5. **安全约束** — 写操作必须 "建议人工确认, 不要自主执行"
6. **诚实约束** — "数据不足时明确说明, 不强行下根因"

---

## 5. 可用工具清单

以下是 `TOOL_META` 中已注册的全部工具。`allowed_tools` 中的名称必须与下表一致。

### 本地工具 (始终可用)

| 工具名 | 只读 | 说明 |
|--------|------|------|
| `search_knowledge_base` | Yes | RAG 知识库检索 |
| `get_current_time` | Yes | 获取当前时间 |

### 本机系统 (MCP `system` 服务器)

| 工具名 | 只读 | 说明 |
|--------|------|------|
| `get_local_system_overview` | Yes | CPU/内存/磁盘整体快照 |
| `get_local_cpu_memory` | Yes | CPU 分核心 + 内存详情 |
| `get_local_disk_usage` | Yes | 磁盘分区使用率 + inode |
| `list_top_processes` | Yes | Top 进程 (按 CPU/内存排序) |

### Windows 事件日志 (MCP `winlog` 服务器)

| 工具名 | 只读 | 说明 |
|--------|------|------|
| `query_windows_event` | Yes | 查询 Windows 事件日志 |

### 联网搜索 (MCP `websearch` 服务器)

| 工具名 | 只读 | 说明 |
|--------|------|------|
| `web_search` | Yes | 联网搜索 (不并发, 避免批量打爆) |

### 网络诊断 (MCP `network` 服务器)

| 工具名 | 只读 | 说明 |
|--------|------|------|
| `ping_host` | Yes | Ping 连通性测试 |
| `http_check` | Yes | HTTP 状态码检测 |
| `dns_lookup` | Yes | DNS 域名解析 |
| `check_port` | Yes | TCP 端口探测 |

### Docker (MCP `docker` 服务器)

| 工具名 | 只读 | 说明 |
|--------|------|------|
| `docker_ps` | Yes | 容器列表 |
| `docker_stats` | Yes | 容器资源占用 |
| `docker_logs` | Yes | 容器日志 |
| `docker_inspect` | Yes | 容器详细配置 |
| `docker_restart` | **No** | 重启容器 (destructive, 需 opt-in) |

### 子代理 (Subagent)

| 工具名 | 只读 | 说明 |
|--------|------|------|
| `delegate_to_evidence_collector` | Yes | 委托收集证据 (指标/日志/进程) |
| `delegate_to_kb_researcher` | Yes | 委托知识库 + 联网研究 |
| `delegate_to_report_writer` | Yes | 委托生成诊断报告 |

### Lazy MCP 元工具

| 工具名 | 只读 | 说明 |
|--------|------|------|
| `mcp_search_tools` | Yes | 搜索可用 MCP 工具 (仅 `mcp_lazy_tools_enabled=true` 时) |
| `mcp_execute_tool` | No | 执行 MCP 工具 (仅 `mcp_lazy_tools_enabled=true` 时) |

---

## 6. 完整示例

### 示例: MySQL 故障诊断 Skill

创建文件 `app/skills/definitions/mysql_diagnosis/SKILL.md`:

```markdown
---
name: mysql_diagnosis
display_name: MySQL 故障诊断
description: 排查 MySQL 连接失败、慢查询、主从延迟、锁等待、OOM 等数据库故障
triggers:
  - mysql
  - 数据库
  - db
  - 慢查询
  - 主从延迟
  - 锁等待
  - 连接超时
  - too many connections
  - deadlock
allowed_tools:
  - search_knowledge_base
  - get_current_time
  - docker_ps
  - docker_logs
  - docker_stats
  - web_search
risk_level: low
---

# MySQL 故障诊断 Playbook

## 适用场景
- MySQL 连接失败 (too many connections / connection refused)
- 慢查询导致业务超时
- 主从复制延迟
- 锁等待 / 死锁
- 数据库 OOM 或异常重启

**不适用**: 应用代码层的 SQL 逻辑问题 (应查应用日志); 非 MySQL 的数据库 (Redis/PostgreSQL)。

## Phase 1: 确认 MySQL 容器状态
1. 调 `docker_ps(filter="mysql")` 确认容器是否在运行
2. 容器不在运行 → 调 `docker_logs(container, tail=100)` 看崩溃原因
3. 容器在运行 → 进入 Phase 2

## Phase 2: 资源检查
1. 调 `docker_stats(container)` 查看 CPU/内存/IO 占用
2. 内存接近 limit → 可能 OOM
3. CPU 持续高 → 可能全表扫描或锁竞争

## Phase 3: 日志分析
1. 调 `docker_logs(container, tail=200)` 获取最近日志
2. 关注:
   - `Too many connections` → 连接池配置问题
   - `Deadlock found` → 事务设计问题
   - `Lock wait timeout` → 长事务或大表 DDL
   - `OOM` / `Killed` → 内存不足

## Phase 4: 知识库参考
1. 调 `search_knowledge_base` 查找相关 SOP
2. 仅作思路参考, 不直接照搬命令

## Phase 5: 输出报告
**现状**: 容器状态、资源占用、关键日志
**根因**: 基于日志和资源数据的判断
**止损**: 连接池调参 / kill 慢事务 / 临时扩容
**优化**: 索引优化 / 连接池配置 / 监控告警

## 注意事项
- 不要自主执行 `docker restart`, 必须建议人工确认
- 慢查询判断需要看具体 SQL, 不能只看"查询多就是慢"
- 主从延迟需要确认 Seconds_Behind_Master 具体值
```

---

## 7. 注册与生效

### 自动注册

Skill 是**零配置自动注册**的:

1. 在 `app/skills/definitions/` 下创建目录 (如 `mysql_diagnosis/`)
2. 在目录中放入 `SKILL.md`
3. 重启服务

启动时 `registry.py` 会自动扫描并加载。日志中会看到:

```
[skill:registry] 已加载 5 个 Skill: generic_oncall, host_resource_diagnosis, mysql_diagnosis, ...
```

### 前端自动展示

- **工作台**: `GET /api/v1/skills` 返回所有 Skill, 前端自动渲染卡片
- **智能诊断页**: Skill 栏自动显示所有 Skill 的 chip
- **诊断历史**: 记录中自动标注使用的 Skill

### 不需要改的文件

- 不需要改 `config.py`
- 不需要改 `graph.py`
- 不需要改 `skill_router.py`
- 不需要改前端代码

---

## 8. 高级: 新增自定义工具

如果你的 Skill 需要调用一个系统中没有的工具 (如专用的 MySQL 诊断 MCP), 需要额外操作:

### 8.1 新增 MCP 服务器 (推荐)

1. 实现一个 MCP server, 暴露所需工具
2. 在 `config.py` 中添加连接配置:
   ```python
   mcp_mysql_transport: str = Field(default="streamable-http")
   mcp_mysql_url: str = Field(default="http://localhost:8012/mcp")
   ```
3. 在 `Settings.mcp_servers` 属性中添加映射:
   ```python
   "mysql": {
       "transport": self.mcp_mysql_transport,
       "url": self.mcp_mysql_url,
   },
   ```
4. 在 `app/tools/meta.py` 的 `TOOL_META` 中注册元数据:
   ```python
   "mysql_query": ToolMeta(
       read_only=True,
       concurrency_safe=True,
       max_result_chars=8000,
       risk_level="low",
       search_hint="mysql query sql 查询",
   ),
   ```
5. 在 SKILL.md 的 `allowed_tools` 中引用工具名

### 8.2 新增本地工具

1. 在 `app/tools/` 下实现工具函数
2. 在工具注册处 (如 `mcp_loader.py`) 注册
3. 在 `TOOL_META` 中注册元数据
4. 在 SKILL.md 的 `allowed_tools` 中引用

### 8.3 元数据字段说明

```python
ToolMeta(
    read_only=True,           # True = 不修改外部状态 (查询类)
    concurrency_safe=True,    # True = 可与其他工具并行执行
    destructive=False,        # True = 不可逆操作 (重启/删除)
    side_effect="none",       # none / external / filesystem / network
    risk_level="low",         # low / medium / high
    max_result_chars=8000,    # 输出截断阈值 (字符)
    search_hint="...",        # ToolSearch 关键字 (可选)
)
```

**重要**: 未在 `TOOL_META` 中注册的工具会按保守默认处理 (`read_only=False`, `concurrency_safe=False`), 可能影响并行编排和权限决策。新增工具务必注册。

---

## 9. 调试与验证

### 9.1 验证 Skill 加载

启动服务后访问 API:

```bash
curl http://localhost:9900/api/v1/skills | python -m json.tool
```

确认你的 Skill 出现在列表中。

### 9.2 测试路由

在"智能诊断"页面输入一个应该命中你 Skill 的问题, 观察:
- Skill 栏是否高亮了正确的 Skill
- 日志中是否有 `[skill_router] 选择 skill=your_new_skill`

### 9.3 测试工具可用性

如果诊断过程中工具调用失败, 检查:
- MCP 服务器是否启动 (`curl http://localhost:<port>/mcp`)
- 工具名是否与 MCP 服务器暴露的名称完全一致
- `TOOL_META` 中是否注册了该工具

### 9.4 常见问题

| 问题 | 原因 | 解决 |
|------|------|------|
| Skill 未加载 | SKILL.md 路径错误或 YAML 格式有误 | 检查日志中的 `SkillLoadError` |
| Router 选错 Skill | description 不够明确 | 改善 description, 区分边界 |
| 工具调用被拒绝 | 工具不在 allowed_tools 中 | 检查工具名拼写 |
| 工具返回空 | MCP 服务器未启动 | 确认 MCP server 在运行 |
| 报告质量差 | Playbook 步骤不够具体 | 补充具体工具调用和判断逻辑 |
