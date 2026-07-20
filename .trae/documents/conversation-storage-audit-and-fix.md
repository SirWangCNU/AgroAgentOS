# 对话历史存储机制排查与改造方案

> 用户决策（已确认）：
>
> 1. **应用 = 对话会话本身**：session\_id 即为应用 ID，无需引入新实体。
> 2. **前端范围**：React 前端 + 微信小程序均改造。
> 3. **缓存策略**：升级为多级缓存（DB 持久层 + Redis 热数据 + 进程内 LRU 缓存）。

***

## 一、当前状态分析（Phase 1 探索结论）

### 1.1 存储架构现状（4 层碎片化）

| 层级         | 文件                                                      | 用途        | 隔离方式                                          | 持久化           |
| ---------- | ------------------------------------------------------- | --------- | --------------------------------------------- | ------------- |
| SQLite 持久层 | `app/core/sqlite.py` + `app/models/session.py`          | 对话会话与消息落盘 | session\_id                                   | ✅ 永久          |
| Redis 缓存层  | `app/services/chat_memory.py`                           | RAG 上下文记忆 | `rag:chat:{sha256(session_id)[:32]}:messages` | ❌ TTL（默认 24h） |
| 进程内 TTL 缓存 | `app/services/session_service.py`                       | 减少 DB IO  | 全局失效（致命缺陷）                                    | ❌ 5s/30s      |
| 独立诊断历史表    | `app/services/history_service.py` + `history_records` 表 | 诊断记录归档    | record\_id                                    | ✅ 永久          |

### 1.2 数据模型现状

**`chat_sessions`** **表**（定义在两处，`extend_existing=True` 合并）：

* `app/core/sqlite.py:52-73` — 带 `extra_json` + `@property extra` 访问器

* `app/models/session.py:10-22` — 无 `extra` 访问器

* 字段：`session_id` (UUID), `user_id`, `title`, `created_at`, `updated_at`, `extra_json`

* **无** **`app_id`/`agent_id`** **字段**（用户已确认应用=会话，故无需新增）

**消息表存在两套（严重设计冲突）：**

| 表名                      | 定义位置                          | FK 级联                  | 字段                                         | 使用方                                                   |
| ----------------------- | ----------------------------- | ---------------------- | ------------------------------------------ | ----------------------------------------------------- |
| `chat_messages`         | `app/core/sqlite.py:76-96`    | ❌ 无 FK                 | role, content, created\_at, extra\_json    | `database_manager.save_message()`（旧路径，未被 chat API 调用） |
| `chat_session_messages` | `app/models/session.py:25-37` | ✅ `ondelete="CASCADE"` | role, content, **image\_url**, created\_at | `SessionService`（`/sessions` API 使用）                  |

**`PRAGMA foreign_keys=ON`** 已在 `app/core/sqlite.py:335` 和 `app/core/database.py:88` 启用，FK 级联可生效。

### 1.3 已识别的 BUG 与风险（共 15 项，按严重度排序）

#### 🔴 严重 BUG（违反核心需求）

**BUG-1：小程序对话历史完全不可用**

* 位置：`agroagent-miniapp/miniprogram/pages/chat/conversation.js:18`

* 现象：每次进页面生成新 `sessionId = mp_${Date.now()}_${random}`，从不加载历史，AI 消息从不持久化

* `q` URL 参数自动触发 `send()`（行 22-26）— 即用户提到的"浏览别人应用意外触发对话"

* 违反需求 1（AI 消息不持久化）、需求 3（不加载历史、无历史不发初始化提示词）

**BUG-2：双消息表并存，数据分裂**

* `chat_messages`（旧）无 FK 无级联；`chat_session_messages`（新）有 FK+CASCADE

* 两表均由 `Base.metadata.create_all()` 创建，DB 中同时存在

* 若有遗留代码走 `database_manager.save_message()`，消息会进错表，前端查不到

* 违反需求 2（删除应用关联删除消息不可靠）

**BUG-3：AI 消息持久化链路脆弱**

* `app/api/v1/chat.py:76-93` 只兜底持久化 **user** 消息

* `app/services/rag_service.py:455-465` 把 user + assistant 写入 **Redis**（非 DB）

* DB 持久化 assistant 完全依赖前端 `addSessionMessage(role=assistant)` 调用

* `frontend-react/src/pages/Chat.tsx:294-296` 用 `.catch(() => {})` 吞掉错误

* **AI 失败时（`ev.type === "error"`）从不记录错误信息**

* 违反需求 1（"即使 AI 回复失败，也要记录错误信息"）

**BUG-4：无分页，全量加载消息**

* `app/services/session_service.py:171-176` `get_session` 用 `.all()` 一次返回所有消息

* 违反需求 3（"每次加载最新 10 条，支持向前加载"）

**BUG-5：chat.py 兜底持久化未校验 session 归属**

* `app/api/v1/chat.py:78-87` 调用 `session_service.get_session(req.session_id, user_id)` 看似校验了

* 但 `session_service.add_message(session_uuid, ...)` 内部不校验 user\_id（`session_service.py:239-270`）

* 若前端传入他人 session\_id，可在他人会话写消息（越权风险）

#### 🟡 中等风险

**RISK-6：进程内缓存全局失效**

* `app/services/session_service.py:58-61` `_invalidate_session_caches()` 清空所有用户的所有会话缓存

* 每条新消息都触发全清，高并发下缓存命中率趋零

**RISK-7：Redis 与 DB 双写不一致**

* `chat_memory.append_message` 写 Redis 失败时仅 warning（`chat_memory.py:150-151`）

* Redis TTL 过期后 RAG 上下文丢失历史，但 DB 仍有 — 双数据源未对账

* `chat_memory.load_session` 只读 Redis 不读 DB

**RISK-8：小程序 URL 参数触发对话**

* `agroagent-miniapp/miniprogram/pages/chat/home.js:57-60` 用 `wx.navigateTo` 携带 `q` 参数

* `conversation.js:22-26` 见到 `q` 立即 `send()` — 用户体验上"刚点进应用就开始对话"

**RISK-9：`chat_session_messages`** **无错误元数据字段**

* 表只有 role/content/image\_url/created\_at，无法记录 `status=error`、`error_message`、tokens 等元数据

**RISK-10：`auto_title_from_message`** **依赖中文字面量**

* `session_service.py:281` `if session.title == "新对话":` — 字符串硬编码，脆弱

#### 🟢 轻微问题

**RISK-11**：`rag_service` 重复写 history\_records 表（与 chat\_session\_messages 内容重叠）
**RISK-12**：小程序 `chat-bubble.wxml:1` 行 14 `<view wx:else class="text">{{content}}</view>` — 流式更新时 setData 频繁，性能差
**RISK-13**：`sessions.py:96-108` `add_message` API 用 URLSearchParams 传 content，长消息可能超 URL 长度限制
**RISK-14**：`ChatSession.extra_json` 在 `app/models/session.py` 版本无 `@property` 访问器，违反 AGENTS.md `_json` 后缀模式约定
**RISK-15**：前端 `conversation.ts:160-171` 用 `role:content.slice(0,100)` 去重合并消息，长相同前缀的不同消息会被误判

### 1.4 需求合规性矩阵

| 需求             | 状态                | 关键证据                                                    |
| -------------- | ----------------- | ------------------------------------------------------- |
| 1) 持久化 user 消息 | ✅ 已实现             | `chat.py:85-87` + 前端 `addSessionMessage`                |
| 1) 持久化 AI 消息   | ⚠️ 部分             | 仅前端 POST，后端不主动落盘；失败更不落盘                                 |
| 1) AI 失败记录错误   | ❌ 未实现             | 无任何错误消息持久化路径                                            |
| 2) 应用级隔离       | ✅ 已实现             | 按 session\_id 隔离（用户已确认应用=会话）                            |
| 2) 删除应用级联删除    | ⚠️ 部分             | `chat_session_messages` FK 级联生效，但 `chat_messages` 旧表不级联 |
| 3) 分页查最新10条    | ❌ 未实现             | `get_session` 全量返回                                      |
| 3) 向前加载更多      | ❌ 未实现             | 无 API 无参数                                               |
| 3) 进入应用先加载历史   | ⚠️ React 部分；小程序 ❌ | React `Chat.tsx:91-128` 加载但无分页；小程序完全不加载                 |
| 3) 无历史才发初始化提示词 | ❌ 未实现             | 小程序见 `q` 即发；React 无此逻辑                                  |

***

## 二、改造方案

### 2.1 后端数据模型改造

#### 改动 1：统一消息表，废弃 `chat_messages` 旧表

**文件**：`app/core/sqlite.py`、`app/models/session.py`

**问题**：当前 `ChatMessage`（`chat_messages` 表）和 `ChatSessionMessage`（`chat_session_messages` 表）并存。

**方案**：

* 保留 `app/models/session.py` 中的 `ChatSessionMessage` 作为唯一权威消息表

* 在 `app/core/sqlite.py` 中删除 `ChatMessage` 类（行 76-96）— 它仅被 `database_manager.save_message()` 使用，但该方法未被任何 chat API 调用（已验证）

* 同步删除 `DatabaseManager.save_message` 和 `get_messages` 方法（`database.py:176-205`），以及 `SQLiteManager.save_message` 和 `get_messages`（`sqlite.py:373-400`）

* 写一次性数据迁移脚本 `scripts/migrate_chat_messages.py`：把 `chat_messages` 表中遗留数据搬到 `chat_session_messages`，再 DROP 旧表

* 提供 Alembic 迁移 `010_unify_chat_messages.py` 记录此次变更

**验证**：`pytest tests/services/` 全绿；启动后 `Base.metadata.create_all` 不再创建 `chat_messages` 表

#### 改动 2：`ChatSessionMessage` 增加元数据字段

**文件**：`app/models/session.py`、`app/schemas/session.py`

**问题**：当前表无 `status`/`error_message`/`extra_json`，无法记录错误信息和 token 用量。

**方案**：在 `ChatSessionMessage` 上增加：

```python
status = Column(String(16), nullable=False, default="success")  # success / error / partial
error_message = Column(Text, nullable=True)                      # AI 失败时的错误信息
extra_json = Column(Text, nullable=True)                         # tokens/sources/rewritten_query 等元数据

@property
def extra(self) -> dict[str, Any]:
    if not self.extra_json:
        return {}
    try:
        return json.loads(self.extra_json)
    except Exception:
        return {}

def set_extra(self, data: dict[str, Any]) -> None:
    self.extra_json = json.dumps(data, ensure_ascii=False, default=str)
```

* 同时给 `app/models/session.py` 中的 `ChatSession` 补 `extra`/`set_extra` 属性，对齐 `app/core/sqlite.py` 的实现（修复 RISK-14）

* Alembic 迁移：`011_add_message_metadata.py` 增加 3 列

**验证**：迁移成功；`MessageOut` schema 暴露新字段

#### 改动 3：`SessionService` 重写 — 支持分页、错误消息、多级缓存

**文件**：`app/services/session_service.py`、`app/schemas/session.py`

**问题**：当前 `get_session` 全量返回消息；`add_message` 不校验归属；缓存全局失效。

**方案 A — 分页查询 API**：

新增 `get_session_messages_paginated` 方法：

```python
def get_session_messages_paginated(
    self, session_uuid: str, user_id: int,
    *, limit: int = 10, before_id: int | None = None,
) -> dict:
    """游标分页：返回最新 limit 条，或 before_id 之前的 limit 条。
    
    Returns: {"messages": [...], "has_more": bool, "oldest_id": int|None}
    """
```

* 首次加载：`ORDER BY id DESC LIMIT 10`，返回时反转为 ASC

* 向前加载：`WHERE id < before_id ORDER BY id DESC LIMIT 10`

* `has_more` 通过额外查 1 条（`LIMIT 11` 取 10）判断

**方案 B — 错误消息持久化**：

新增 `add_error_message` 方法：

```python
def add_error_message(
    self, session_uuid: str, user_id: int,
    *, content: str, error_message: str, extra: dict | None = None,
) -> MessageOut:
    """AI 失败时持久化 assistant 错误消息。"""
    # role="assistant", status="error", error_message=...
```

**方案 C — 多级缓存（DB + Redis + 进程内 LRU）**：

替换现有 `_TTLCache` 全局失效逻辑：

```python
from functools import lru_cache
# 进程内 LRU：按 session_uuid 精确缓存最近 N 个会话的消息列表
# Redis：缓存最新 50 条消息（热数据），TTL 1h
# DB：权威源

class _SessionCache:
    """按 session_uuid 精确失效的 LRU 缓存。"""
    def __init__(self, maxsize: int = 256, ttl: int = 30) -> None: ...
    def get(self, session_uuid: str, key: str) -> object | None: ...
    def set(self, session_uuid: str, key: str, value: object) -> None: ...
    def invalidate_session(self, session_uuid: str) -> None:  # 仅清该 session
        ...
```

失效策略从"全清"改为"按 session\_uuid 精确清"。

**方案 D —** **`add_message`** **强制校验归属**：

```python
def add_message(self, session_uuid: str, user_id: int, role: str, content: str, ...):
    with sqlite_manager.session() as sess:
        session = sess.query(ChatSession).filter(
            ChatSession.session_id == session_uuid,
            ChatSession.user_id == str(user_id),  # 新增校验
        ).first()
        if not session:
            raise ValueError(f"会话不存在或不属于该用户: {session_uuid}")
```

* 修复 BUG-5 越权风险

* 调用方需传 `user_id`（`sessions.py` 的 API 已有 `current_user`，`chat.py` 兜底持久化需补 `user_id` 参数）

**验证**：

* `pytest tests/services/test_session_service.py`（新增）覆盖分页、错误消息、缓存失效

* 手动测试：删除某 session 后，其他 session 的缓存仍命中

### 2.2 后端 API 改造

#### 改动 4：新增分页查询端点

**文件**：`app/api/v1/sessions.py`、`app/schemas/session.py`

新增端点：

```python
@router.get("/{session_id}/messages", summary="分页查询会话消息")
async def list_messages(
    session_id: str,
    limit: int = 10,        # 默认 10，最大 50
    before_id: int | None = None,  # 游标：返回 id < before_id 的消息
    current_user: User = Depends(get_current_user),
) -> ApiResponse:
    data = session_service.get_session_messages_paginated(
        session_id, current_user.id, limit=limit, before_id=before_id
    )
    return ApiResponse.success(data=data)
```

保留原 `GET /sessions/{id}` 用于会话元信息（不含消息），避免详情接口承载过重。

#### 改动 5：`chat.py` 兜底持久化修复越权 + 错误消息持久化

**文件**：`app/api/v1/chat.py`

**问题**：兜底持久化未传 `user_id`；SSE 错误事件不持久化。

**方案**：

* `session_service.add_message(req.session_id, user_id, "user", ...)` — 传入 `user_id` 触发归属校验

* 在 `event_generator` 的 `except` 分支增加错误消息持久化：

```python
except Exception as e:
    logger.exception(f"[chat] stream 异常: {e}")
    # 新增：持久化错误消息到 DB
    if user_id is not None and req.session_id:
        try:
            session_service.add_error_message(
                req.session_id, user_id,
                content=full_answer or "（AI 回复失败）",
                error_message=f"{type(e).__name__}: {e}",
            )
        except Exception as persist_err:
            logger.warning(f"[chat] 错误消息持久化失败: {persist_err}")
    yield {"event": "message", "data": json.dumps({"type": "error", "message": str(e)}, ensure_ascii=False)}
```

* 需在 `stream_chat` 内部累加 `full_answer` 后传出，或在 `chat.py` 维护累加器

**备选**：在 `rag_service.stream_chat` 内部错误分支直接调用 `session_service.add_error_message`，避免在 `chat.py` 重新累加 tokens。**推荐此方案**（职责更清晰）。

#### 改动 6：`rag_service.stream_chat` 完成时主动持久化 assistant 消息到 DB

**文件**：`app/services/rag_service.py`

**问题**：当前只写 Redis（`chat_memory.append_message`），不写 DB；DB 写完全靠前端。

**方案**：在 `stream_chat` 收尾阶段（行 454-478 附近），除了写 Redis 和 history\_records，再调用 `session_service.add_message(session_id, user_id, "assistant", full_answer, extra={...})` 主动落盘。

**关键决策**：

* 需要把 `user_id` 透传到 `stream_chat`（当前已有 `user_id` 参数）

* 但 `session_service.add_message` 需要 `session_uuid` 存在于 `chat_sessions` 表 — `chat.py` 兜底已确保 user 消息写入时 session 已存在

* 注意：前端 React 仍会调用 `addSessionMessage(role=assistant)`，需做幂等去重（按 `role+content` 前缀，参考 `conversation.ts:160-171`）— 或在前端移除该调用，由后端统一持久化（**推荐**：后端统一负责，前端不再 POST assistant 消息）

**幂等保护**：`session_service.add_message` 内部检查 `(session_id, role, content[:200])` 在最近 5 秒内是否已存在，避免重复。

### 2.3 多级缓存实现

#### 改动 7：扩展 `chat_memory.py` 为多级缓存

**文件**：`app/services/chat_memory.py`、`app/config.py`

**问题**：当前 Redis 仅做 RAG 上下文记忆，TTL 后丢失；不读 DB。

**方案**：保留 Redis 作为热数据缓存，新增"DB fallback"逻辑：

```python
async def get_messages(session_id: str) -> list[dict[str, Any]]:
    """多级读取：Redis → 进程内 LRU → DB"""
    # 1. Redis 命中
    client = await _get_redis()
    if client is not None:
        rows = await client.lrange(_messages_key(session_id), 0, -1)
        if rows:
            return [_sanitize_message(json.loads(r)) for r in rows if ...]
    # 2. 进程内 LRU（已由 SessionService 管理，此处可省略）
    # 3. DB fallback — 新增
    from app.services.session_service import session_service
    # 注意：chat_memory 是 async，session_service 是 sync，需 asyncio.to_thread
    ...
```

**新增配置项**（`app/config.py`）：

* `chat_cache_redis_ttl_sec: int = 3600` — Redis 热数据 TTL（1 小时，比 RAG memory 长）

* `chat_cache_lru_maxsize: int = 256` — 进程内 LRU 容量

**关键约束**：

* Redis 失败时降级读 DB（已具备 `_get_redis() is None` 判断）

* 写入路径：DB → Redis（先 DB 后 Redis，DB 是权威源）

* `clear_session` 同步清 Redis + DB（DB 通过 `session_service.delete_session`）

### 2.4 React 前端改造

#### 改动 8：分页加载历史消息

**文件**：`frontend-react/src/api/sessions.ts`、`frontend-react/src/stores/conversation.ts`、`frontend-react/src/pages/Chat.tsx`

**方案**：

1. `sessions.ts` 新增 `listMessages(sessionId, { limit, beforeId })` 函数
2. `conversation.ts` 改造 `loadMessages`：

   * 默认只加载最新 10 条（调用新分页 API）

   * 新增 `loadMoreMessages(sessionId)` action：基于 `oldest_id` 游标加载更早 10 条，prepend 到 `messages`

   * 状态新增 `hasMore: boolean`、`oldestLoadedId: number | null`、`loadingMore: boolean`
3. `Chat.tsx`：

   * 在消息列表顶部增加"加载更多"按钮（仅 `hasMore` 时显示）

   * 移除前端调用 `addSessionMessage(role=assistant)` 的代码（行 294-296），由后端统一持久化

   * 加载历史时若有消息则展示，无消息显示欢迎页（已有逻辑保留）

#### 改动 9：移除前端 assistant 消息持久化调用

**文件**：`frontend-react/src/pages/Chat.tsx:294-296`、`frontend-react/src/stores/conversation.ts:266`

**问题**：前端 POST assistant 消息易丢失（`.catch(() => {})`），且与后端新增的主动持久化重复。

**方案**：

* 删除 `Chat.tsx:294-296` 的 `addSessionMessage(convId, "assistant", assistantContent)`

* 删除 `conversation.ts` 中 `addMessage` 对 assistant 角色的后端 POST（保留 user 角色的 POST，因 React 端 user 消息需立即落盘以支持后端 SSE 上下文）

* 用户消息保留前端 POST（与后端兜底持久化形成双保险，幂等去重已在 `chat.py:80-83` 实现）

### 2.5 微信小程序改造

#### 改动 10：重写小程序对话页面（核心修复）

**文件**：`agroagent-miniapp/miniprogram/pages/chat/conversation.js`、`conversation.wxml`、`home.js`、`app.js`

**问题**：随机 sessionId、不加载历史、`q` 参数自动触发对话、AI 消息不持久化。

**方案**：

**A. 稳定 sessionId 策略**：

* 进入对话页时，先从 `wx.getStorageSync('last_session_id')` 读取

* 若无，调用后端 `POST /sessions` 创建新会话，存入 storage

* 用户可在头部菜单"新建对话"清空 storage 并重新创建

```javascript
// conversation.js onLoad 重写
async onLoad(query) {
  const sys = wx.getWindowInfo();
  this.setData({ statusBarHeight: sys.statusBarHeight || 20 });
  
  // 1. 加载或创建 session
  let sessionId = wx.getStorageSync('last_session_id');
  if (!sessionId) {
    try {
      await app.ensureLogin();
      const session = await createSession();  // 调用 /sessions
      sessionId = session.id;
      wx.setStorageSync('last_session_id', sessionId);
    } catch (err) {
      wx.showToast({ title: '初始化失败', icon: 'none' });
      return;
    }
  }
  this.setData({ sessionId });
  
  // 2. 加载历史消息（最新 10 条）
  await this.loadHistory();
  
  // 3. 仅当无历史 + 携带 q 参数时才自动发送初始化提示词
  const q = query.q ? decodeURIComponent(query.q) : '';
  if (q && this.data.messages.length === 0) {
    this.setData({ inputText: q });
    this.send(q);
  } else if (q) {
    // 有历史则只填入输入框，不自动发送
    this.setData({ inputText: q });
  }
}

async loadHistory(beforeId) {
  const data = await listMessages(this.data.sessionId, { limit: 10, beforeId });
  const newMsgs = data.messages.map(m => ({
    role: m.role, content: m.content, thinking: false, sources: [], progress: ''
  }));
  this.setData({
    messages: beforeId ? [...newMsgs.reverse(), ...this.data.messages] : newMsgs.reverse(),
    hasMore: data.has_more,
    oldestId: data.messages[0]?.id || null,
  });
  this.scrollToBottom();
}
```

**B. 新增小程序 API 封装**：

* `agroagent-miniapp/miniprogram/services/api.js`（新建）：封装 `createSession`、`listMessages`、`addSessionMessage`

* 复用 `services/sse.js` 的 `stream`

**C.** **`home.js`** **调整**：

* 不再用 `wx.navigateTo` 携带 `q` 自动触发对话（除非用户主动点击发送）

* 快捷入口跳转时仅填入预设问题到输入框，由用户主动点击发送

**D. chat-bubble 组件优化**：

* 流式 token 更新时减少 `setData` 频率（节流到 100ms 一次）

#### 改动 11：小程序 AI 消息持久化

**文件**：`agroagent-miniapp/miniprogram/pages/chat/conversation.js`

**问题**：当前 `onDone` 只更新 UI，从不调用 `addSessionMessage`。

**方案**：

* `onDone` 回调中调用 `addSessionMessage(sessionId, 'assistant', aiContent)`

* `onError` 回调中也调用 `addSessionMessage`（后端需支持错误消息字段，见改动 2）

* 由于改动 6 让后端 `rag_service` 主动持久化 assistant，小程序其实可以不调用 — 但为保险仍保留（幂等去重由后端处理）

**关键决策**：小程序与 React 一致，**user 消息由前端 POST，assistant 消息由后端主动持久化**。小程序的 `addSessionMessage` 仅作为 user 消息的持久化路径。

### 2.6 数据迁移

#### 改动 12：Alembic 迁移 + 数据搬迁脚本

**文件**：`alembic/versions/010_unify_chat_messages.py`、`alembic/versions/011_add_message_metadata.py`、`scripts/migrate_chat_messages.py`

**010 迁移**：DROP 旧 `chat_messages` 表（若存在），保留 `chat_session_messages`
**011 迁移**：给 `chat_session_messages` 增加 `status`、`error_message`、`extra_json` 列

**迁移脚本**：

```python
# scripts/migrate_chat_messages.py
"""把 chat_messages 旧表数据搬到 chat_session_messages，再 DROP 旧表。"""
# 1. SELECT * FROM chat_messages
# 2. 对每条记录，INSERT INTO chat_session_messages (session_id, role, content, created_at)
#    注意：旧表无 image_url，置 NULL
# 3. DROP TABLE chat_messages
# 4. 记录搬迁数量到日志
```

**验证**：迁移后 `SELECT count(*) FROM chat_messages` 应报错（表不存在）；`chat_session_messages` 行数 ≥ 原 `chat_messages` 行数。

***

## 三、实施步骤（推荐顺序）

| 步骤 | 改动            | 文件                                | 估时    | 风险      |
| -- | ------------- | --------------------------------- | ----- | ------- |
| 1  | 改动 2 + 改动 12  | `app/models/session.py` + 迁移      | 30min | 低（仅加列）  |
| 2  | 改动 1          | 删除 `ChatMessage` 旧类 + 迁移脚本        | 1h    | 中（数据搬迁） |
| 3  | 改动 3          | `session_service.py` 重写（分页+缓存+校验） | 2h    | 中       |
| 4  | 改动 4 + 改动 5   | API 端点 + chat.py 越权修复             | 1h    | 低       |
| 5  | 改动 6 + 改动 7   | rag\_service 主动持久化 + 多级缓存         | 2h    | 高（涉及流式） |
| 6  | 改动 8 + 改动 9   | React 前端分页 + 移除 assistant POST    | 1.5h  | 中       |
| 7  | 改动 10 + 改动 11 | 小程序对话重写                           | 2h    | 中       |
| 8  | 验证            | 测试 + 手动验证                         | 1h    | —       |

**总计**：约 10.5 小时

***

## 四、假设与决策

### 4.1 关键决策

1. **应用 = 对话会话**：用户已确认。`session_id` 即应用 ID，无需新增 `app_id` 字段。需求 2 的"应用级隔离"通过现有 `session_id` 隔离即可满足；"删除应用级联删除"通过 `chat_session_messages` 的 FK CASCADE 已生效（仅需废弃旧 `chat_messages` 表）。

2. **后端统一持久化 assistant 消息**：移除前端 POST assistant 的责任，由 `rag_service.stream_chat` 在收尾阶段主动写 DB。降低前端复杂度，避免 fire-and-forget 丢失。

3. **user 消息保留双写**：前端 POST + 后端 SSE 兜底（已实现），靠 `chat.py:80-83` 的 `(role, content)` 幂等去重。

4. **多级缓存读取顺序**：Redis 热数据 → 进程内 LRU → DB。写入顺序：DB → Redis（DB 是权威源）。Redis 失败时降级读 DB，不影响功能。

5. **分页采用游标方案**：`before_id` 游标比 offset 更稳定（不受新消息插入影响）。首次加载 `LIMIT 10 ORDER BY id DESC`，向前加载 `WHERE id < before_id LIMIT 10`。

6. **小程序 sessionId 持久化到** **`wx.storage`**：用户多次进出对话保持同一 session；"新建对话"按钮显式重置。避免随机 sessionId 导致的历史丢失。

7. **错误消息以 assistant 角色存储**：`role="assistant", status="error"`，前端按 `status` 字段区分渲染（红色错误样式）。

### 4.2 假设

* 现有 `chat_messages` 旧表中数据量很少（未被 chat API 使用），迁移风险低

* Redis 在生产环境可用（`docker compose up -d` 已包含）

* 小程序用户登录态由 `app.ensureLogin()` 管理，无需本方案介入

* 前端 React 用户消息 POST 与后端兜底去重逻辑（`chat.py:80-83` 按 content 完全匹配）能覆盖正常场景；极端并发下可能重复，可接受

### 4.3 不做的事（Out of Scope）

* 不引入新"应用"实体表（用户已确认应用=会话）

* 不重构 `history_records` 表（诊断历史归档，与对话消息解耦）

* 不改造 `Farm Agent` 的 `agent_runs` 表（那是巡检运行记录，不是对话）

* 不引入消息加密 / 软删除（后续需求）

* 不改造 RAG 上下文记忆的压缩逻辑（`compact_if_needed` 保留）

***

## 五、验证步骤

### 5.1 单元测试

新增 `tests/services/test_session_service.py`：

* `test_pagination_latest_10` — 首次加载返回最新 10 条

* `test_pagination_load_more` — `before_id` 游标向前加载

* `test_pagination_has_more_flag` — `has_more` 标记正确

* `test_add_message_ownership_check` — 非会话所有者写入被拒

* `test_add_error_message` — 错误消息以 `status=error` 持久化

* `test_cache_invalidation_per_session` — 仅失效目标 session 的缓存

* `test_cache_redis_fallback_to_db` — Redis 不可用时降级读 DB

### 5.2 集成测试

* `tests/api/test_chat_persistence.py`：

  * SSE 成功后 DB 中存在 user + assistant 消息

  * SSE 异常后 DB 中存在 user + assistant(error) 消息

  * 越权 session\_id 写入返回 403/404

### 5.3 手动验证清单

**React 前端**：

* [ ] 进入空会话 → 显示欢迎页，不自动发送

* [ ] 进入有历史的会话 → 显示最新 10 条，顶部有"加载更多"

* [ ] 点击"加载更多" → prepend 10 条更早消息

* [ ] 发送消息后刷新页面 → user + assistant 消息均在

* [ ] AI 失败（断网/LLM 异常）→ assistant 错误消息以红色显示并持久化

* [ ] 删除会话 → DB 中 `chat_session_messages` 对应行被级联删除

**小程序**：

* [ ] 首次进入对话 → 创建 session，存入 storage，无历史显示欢迎页

* [ ] 从首页点击快捷入口（携带 q）→ 进入对话页，仅填入输入框，**不自动发送**

* [ ] 主动发送一条消息 → 收到回复后退出

* [ ] 再次进入对话页 → 加载历史 10 条，自动滚动到底部

* [ ] 杀进程重进 → 仍是同一 session，历史仍在

* [ ] 点击"新建对话" → 重置 session，历史清空

**缓存验证**：

* [ ] 首次加载会话 → DB 查询一次

* [ ] 30 秒内重复加载 → 进程内缓存命中（无 DB 查询）

* [ ] 清进程内缓存 → Redis 命中（无 DB 查询）

* [ ] 清 Redis → DB fallback 正常返回

* [ ] 其他 session 的写入 → 不影响本 session 缓存命中

### 5.4 回归验证

* `pytest tests/services/` 全绿

* `npm run build`（前端）无 TS 错误

* 小程序开发者工具编译无报错

* 启动后端 `uvicorn app.main:app --reload --port 9800`，启动前端 `npm run dev`，端到端走通

***

## 六、关键文件清单（按改动编号）

| 改动 | 文件路径                                                       | 操作                                                                                       |
| -- | ---------------------------------------------------------- | ---------------------------------------------------------------------------------------- |
| 1  | `app/core/sqlite.py`                                       | 删除 `ChatMessage` 类（行 76-96）+ `save_message`/`get_messages` 方法                            |
| 1  | `app/core/database.py`                                     | 删除 `save_message`/`get_messages` 方法                                                      |
| 1  | `scripts/migrate_chat_messages.py`                         | 新建数据搬迁脚本                                                                                 |
| 1  | `alembic/versions/010_unify_chat_messages.py`              | 新建迁移                                                                                     |
| 2  | `app/models/session.py`                                    | `ChatSessionMessage` 加 `status`/`error_message`/`extra_json`；`ChatSession` 补 `extra` 访问器 |
| 2  | `alembic/versions/011_add_message_metadata.py`             | 新建迁移                                                                                     |
| 2  | `app/schemas/session.py`                                   | `MessageOut` 暴露新字段                                                                       |
| 3  | `app/services/session_service.py`                          | 重写：分页、错误消息、多级缓存、归属校验                                                                     |
| 3  | `app/config.py`                                            | 新增 `chat_cache_redis_ttl_sec`、`chat_cache_lru_maxsize`                                   |
| 4  | `app/api/v1/sessions.py`                                   | 新增 `GET /{id}/messages` 分页端点                                                             |
| 5  | `app/api/v1/chat.py`                                       | 兜底持久化传入 `user_id`；SSE 错误分支持久化错误消息                                                        |
| 6  | `app/services/rag_service.py`                              | 收尾阶段主动持久化 assistant 消息到 DB                                                               |
| 7  | `app/services/chat_memory.py`                              | 多级缓存读取（Redis → DB fallback）                                                              |
| 8  | `frontend-react/src/api/sessions.ts`                       | 新增 `listMessages(sessionId, {limit, beforeId})`                                          |
| 8  | `frontend-react/src/stores/conversation.ts`                | `loadMessages` 改为分页；新增 `loadMoreMessages`                                                |
| 8  | `frontend-react/src/pages/Chat.tsx`                        | 顶部"加载更多"按钮                                                                               |
| 9  | `frontend-react/src/pages/Chat.tsx`                        | 删除行 294-296 的 `addSessionMessage(assistant)`                                             |
| 9  | `frontend-react/src/stores/conversation.ts`                | `addMessage` 仅 POST user 角色                                                              |
| 10 | `agroagent-miniapp/miniprogram/pages/chat/conversation.js` | 重写：稳定 sessionId + 加载历史 + 无历史才发                                                           |
| 10 | `agroagent-miniapp/miniprogram/pages/chat/home.js`         | 快捷入口不自动触发对话                                                                              |
| 10 | `agroagent-miniapp/miniprogram/services/api.js`            | 新建：封装 sessions API                                                                       |
| 11 | `agroagent-miniapp/miniprogram/pages/chat/conversation.js` | `onDone`/`onError` 持久化 assistant 消息                                                      |
| 12 | `alembic/versions/010_unify_chat_messages.py`              | 见改动 1                                                                                    |
| 12 | `alembic/versions/011_add_message_metadata.py`             | 见改动 2                                                                                    |

***

## 七、风险与回滚

### 7.1 主要风险

1. **数据迁移风险**：搬迁 `chat_messages` → `chat_session_messages` 时若中断可能数据不一致

   * 缓解：迁移脚本包裹事务；搬迁后再 DROP 旧表；保留 7 天 backup
2. **后端主动持久化 assistant 与前端 POST 重复**：可能产生重复消息

   * 缓解：`session_service.add_message` 内部 `(session_id, role, content[:200], created_at ± 5s)` 幂等去重
3. **小程序 storage 被用户清除**：sessionId 丢失，历史"看似"消失

   * 缓解：sessionId 也服务端可查（`GET /sessions` 列表），用户可在"历史会话"入口找回
4. **多级缓存一致性**：DB 写成功但 Redis 写失败

   * 缓解：Redis 写失败仅 warning 不阻塞；下次读时 Redis miss 自动从 DB 回填

### 7.2 回滚方案

* Alembic 迁移可 `alembic downgrade -1` 回退

* `ChatMessage` 旧类删除可通过 git revert 恢复

* 前端改动通过 git 分支隔离，必要时回退分支

* 小程序改动通过 git 分支隔离

***

## 八、合规性检查（遵守 AGENTS.md）

* ✅ **最小范围修改**：每项改动都有明确文件和行号，不顺手重构无关代码

* ✅ **分层规则**：路由 → 服务 → 模型，未跨层直接 DB 调用

* ✅ **类型规则**：所有新方法有类型注解；Pydantic schema 同步更新

* ✅ **错误处理**：错误消息持久化不吞异常（`logger.warning` + 返回 None/False）

* ✅ **测试规则**：新增 `tests/services/test_session_service.py` 覆盖核心逻辑

* ✅ **迁移规则**：使用 Alembic 而非手动改表

* ✅ **中文注释**：保持现有中文注释风格

* ✅ **`_json`** **后缀模式**：新增 `extra_json` 配套 `@property extra` + `set_extra` 访问器

* ✅ \*\*不绕过类型/迁移/吞

