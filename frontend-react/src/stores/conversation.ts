import { create } from "zustand";
import type { ChatMessage, Citation } from "../types/chat";
import type { ProgressStep } from "../components/chat/ProgressSteps";
import {
  createSession,
  listSessions,
  deleteSession,
  updateSession,
  listMessages,
  addSessionMessage,
  type SessionOut,
} from "../api/sessions";

interface Conversation extends SessionOut {
  messages: ChatMessage[];
  /** 是否还有更早的历史消息可加载 (游标分页) */
  hasMoreMessages: boolean;
  /** 当前已加载的最旧消息 id, 作为下次向前加载的 before_id 游标 */
  oldestLoadedId: number | null;
}

interface ConversationState {
  conversations: Conversation[];
  activeId: string | null;
  isStreaming: boolean;
  /**
   * 当前正在流式生成的会话 ID.
   * BUG 修复: 之前 updateLastAssistant/setThinking 等流式更新函数内部用 get().activeId
   * 作为写入目标, 用户切换会话后 activeId 变了, 正在生成的 token 会被写到切换后的新会话.
   * 现在所有流式更新都接受 targetSessionId 参数, 写入"发送时的会话"而不是"当前激活的会话".
   * streamingSessionId 同时用于 UI 判断: 只在 activeId === streamingSessionId 时显示进度.
   */
  streamingSessionId: string | null;
  isLoadingMessages: boolean;
  /** 向前加载更多历史消息的 loading 标记 */
  isLoadingMore: boolean;

  // Chat settings
  webSearch: boolean;
  mcpTools: boolean;

  // Live streaming state
  liveProgress: ProgressStep[];
  liveCitations: Citation[];
  progressPhase: boolean; // true = still in retrieval/search phase

  // Actions
  loadConversations: () => Promise<void>;
  refreshConversations: () => Promise<void>;
  createNew: () => Promise<string>;
  setActive: (id: string | null) => void;
  deleteOne: (id: string) => Promise<void>;
  renameOne: (id: string, title: string) => Promise<void>;
  loadMessages: (id: string) => Promise<void>;
  loadMoreMessages: (id: string) => Promise<void>;
  addMessage: (msg: ChatMessage) => Promise<void>;
  /** targetSessionId 缺省时回落到 activeId (兼容旧调用) */
  updateLastAssistant: (content: string, targetSessionId?: string) => void;
  setThinking: (content: string, targetSessionId?: string) => void;
  setStreaming: (v: boolean, targetSessionId?: string) => void;
  setWebSearch: (v: boolean) => void;
  setMcpTools: (v: boolean) => void;

  // Progress tracking — targetSessionId 用于隔离多会话的流式进度
  addProgressStep: (step: ProgressStep, targetSessionId?: string) => void;
  updateLastProgressStep: (step: Partial<ProgressStep>, targetSessionId?: string) => void;
  setLiveCitations: (citations: Citation[], targetSessionId?: string) => void;
  setProgressPhase: (v: boolean, targetSessionId?: string) => void;
  markAllProgressDone: (targetSessionId?: string) => void;
  clearLiveState: (targetSessionId?: string) => void;

  // Getters
  activeConversation: () => Conversation | null;
}

export const useConversationStore = create<ConversationState>((set, get) => ({
  conversations: [],
  activeId: null,
  isStreaming: false,
  streamingSessionId: null,
  isLoadingMessages: false,
  isLoadingMore: false,
  webSearch: false,
  mcpTools: true,
  liveProgress: [],
  liveCitations: [],
  progressPhase: true,

  loadConversations: async () => {
    try {
      const sessions = await listSessions();
      set({
        conversations: sessions.map((s) => ({
          ...s,
          messages: [],
          hasMoreMessages: false,
          oldestLoadedId: null,
        })),
      });
    } catch (err) {
      console.error("Failed to load conversations:", err);
    }
  },

  refreshConversations: async () => {
    try {
      const sessions = await listSessions();
      set((s) => {
        // Build map of existing local conversations to preserve their messages
        const existingMap = new Map(s.conversations.map((c) => [c.id, c]));
        const serverIds = new Set(sessions.map((sess) => sess.id));
        return {
          conversations: [
            // Server sessions (with local messages preserved if any)
            ...sessions.map((session) => {
              const existing = existingMap.get(session.id);
              return {
                ...session,
                messages: existing?.messages ?? [],
                hasMoreMessages: existing?.hasMoreMessages ?? false,
                oldestLoadedId: existing?.oldestLoadedId ?? null,
              };
            }),
            // Bug fix: 保留本地存在但服务器尚未返回的会话
            // 这种情况通常发生在 listSessions 因时序问题没看到刚刚 createNew 的会话
            // 如果不保留，本地新会话及其所有消息会被整体移除，导致 addMessage 找不到目标会话
            ...s.conversations.filter((c) => !serverIds.has(c.id)),
          ],
        };
      });
    } catch (err) {
      console.error("Failed to refresh conversations:", err);
    }
  },

  createNew: async () => {
    const session = await createSession();
    const conv: Conversation = {
      ...session,
      messages: [],
      hasMoreMessages: false,
      oldestLoadedId: null,
    };
    set((s) => ({
      conversations: [conv, ...s.conversations],
      activeId: conv.id,
    }));
    // Refresh in background to get accurate message_count
    get().refreshConversations().catch(() => {});
    return conv.id;
  },

  setActive: (id) => set({ activeId: id }),

  deleteOne: async (id) => {
    await deleteSession(id);
    set((s) => {
      const filtered = s.conversations.filter((c) => c.id !== id);
      return {
        conversations: filtered,
        activeId: s.activeId === id ? (filtered[0]?.id ?? null) : s.activeId,
      };
    });
  },

  renameOne: async (id, title) => {
    await updateSession(id, title);
    set((s) => ({
      conversations: s.conversations.map((c) =>
        c.id === id ? { ...c, title } : c
      ),
    }));
  },

  loadMessages: async (id) => {
    set({ isLoadingMessages: true });
    try {
      // ✅ 新会话（0条消息）直接跳过请求，避免不必要的接口调用
      const conv = get().conversations.find((c) => c.id === id);
      if (conv && conv.message_count === 0 && conv.messages.length === 0) {
        set({ isLoadingMessages: false });
        return;
      }
      // 首次进入会话只加载最新 10 条 (需求 3: 类似聊天软件的消息加载机制)
      // 向前加载更多历史用 loadMoreMessages (顶部"加载更多"按钮触发)
      const page = await listMessages(id, { limit: 10, beforeId: null });
      const messages: ChatMessage[] = page.messages.map((m) => ({
        role: m.role as "user" | "assistant",
        content: m.content,
        ...(m.image_url ? { imageUrl: m.image_url } : {}),
        ...(m.status && m.status !== "success" ? { status: m.status as "error" | "partial" } : {}),
        ...(m.error_message ? { errorMessage: m.error_message } : {}),
      }));
      set((s) => {
        const existing = s.conversations.find((c) => c.id === id);
        if (existing) {
          // Bug fix: 更稳健的合并策略 —— 保留所有本地消息，用服务器消息补充本地没有的
          // 之前的逻辑基于数量比较，可能在本地流式生成中错误覆盖本地用户消息
          // 现在的逻辑：本地消息全保留，服务器消息中本地没有的（按 role + content 前缀匹配）追加到末尾
          const existingKeys = new Set(
            existing.messages.map(
              (m) => `${m.role}:${(m.content || "").slice(0, 100)}`
            )
          );
          const merged: ChatMessage[] = [...existing.messages];
          for (const serverMsg of messages) {
            const key = `${serverMsg.role}:${(serverMsg.content || "").slice(0, 100)}`;
            if (!existingKeys.has(key)) {
              merged.push(serverMsg);
            }
          }
          return {
            isLoadingMessages: false,
            conversations: s.conversations.map((c) =>
              c.id === id
                ? {
                    ...c,
                    messages: merged,
                    hasMoreMessages: page.has_more,
                    oldestLoadedId: page.oldest_id,
                  }
                : c
            ),
          };
        }
        // Conversation not in store (e.g. direct URL navigation) — add it
        return {
          isLoadingMessages: false,
          conversations: [
            {
              id,
              title: "新对话",
              created_at: new Date().toISOString(),
              updated_at: new Date().toISOString(),
              message_count: messages.length,
              messages,
              hasMoreMessages: page.has_more,
              oldestLoadedId: page.oldest_id,
            },
            ...s.conversations,
          ],
        };
      });
    } catch (err: any) {
      console.error("Failed to load messages:", err);
      // Bug 修复: 404 (会话不存在/已删除) 时不抛错, 改为写入一个空 stub
      // 之前: 抛错 → Chat 组件显示 "对话不存在或已被删除" 整页错误, 用户体验差
      // 现在: 写入一个空消息的 stub → Chat 渲染 welcome 页面 + ChatInput, 用户可立即开始新对话
      if (err?.status === 404) {
        set((s) => {
          const exists = s.conversations.find((c) => c.id === id);
          if (exists) {
            return { isLoadingMessages: false };
          }
          // 写入一个空 stub, 用 sessionId 作为标题, 用户可以基于此继续对话
          return {
            isLoadingMessages: false,
            conversations: [
              {
                id,
                title: "新对话",
                created_at: new Date().toISOString(),
                updated_at: new Date().toISOString(),
                message_count: 0,
                messages: [],
                hasMoreMessages: false,
                oldestLoadedId: null,
              },
              ...s.conversations,
            ],
          };
        });
        return; // 不再 re-throw, 让 Chat 走欢迎页分支
      }
      set({ isLoadingMessages: false });
      throw err; // 其他错误继续向上抛, 让 Chat 显示错误信息
    }
  },

  loadMoreMessages: async (id) => {
    const conv = get().conversations.find((c) => c.id === id);
    if (!conv || !conv.hasMoreMessages || conv.oldestLoadedId == null) {
      return;
    }
    set({ isLoadingMore: true });
    try {
      // 游标分页: 用当前最旧消息 id 作为 before_id, 加载更早的 10 条
      const page = await listMessages(id, {
        limit: 10,
        beforeId: conv.oldestLoadedId,
      });
      const olderMessages: ChatMessage[] = page.messages.map((m) => ({
        role: m.role as "user" | "assistant",
        content: m.content,
        ...(m.image_url ? { imageUrl: m.image_url } : {}),
        ...(m.status && m.status !== "success" ? { status: m.status as "error" | "partial" } : {}),
        ...(m.error_message ? { errorMessage: m.error_message } : {}),
      }));
      set((s) => ({
        isLoadingMore: false,
        conversations: s.conversations.map((c) =>
          c.id === id
            ? {
                ...c,
                // prepend 更早的消息到列表头部
                messages: [...olderMessages, ...c.messages],
                hasMoreMessages: page.has_more,
                oldestLoadedId: page.oldest_id ?? c.oldestLoadedId,
              }
            : c
        ),
      }));
    } catch (err) {
      console.error("[conversation] loadMoreMessages failed:", err);
      set({ isLoadingMore: false });
    }
  },

  addMessage: async (msg) => {
    const { activeId } = get();
    // 防御：如果 activeId 为空，记录警告而不是静默失败
    // 这通常发生在 useEffect 时序问题中 —— createNew 更新了 activeId 但
    // useEffect 在 navigate 完成前就运行了 setActive(null)
    if (!activeId) {
      console.warn(
        "[conversation] addMessage called with no activeId, message dropped:",
        msg
      );
      return;
    }
    // 本地 store 立即更新（乐观更新，UI 即时反馈）
    // 注意：activeId 对应的会话必须已经在 store 里 —— createNew() 是唯一的入口
    // 之前这里有个"会话不存在就新建"的防御分支，会和 refreshConversations 的时序
    // 竞争产生同 id 的孤儿条目（sidebar 出现两条"新对话"），现已删除
    set((s) => {
      const conv = s.conversations.find((c) => c.id === activeId);
      if (!conv) {
        console.error(
          "[conversation] activeId 对应的会话不在 store, 不修改状态以避免重复:",
          activeId
        );
        return s;
      }
      return {
        conversations: s.conversations.map((c) =>
          c.id === activeId
            ? { ...c, messages: [...c.messages, msg] }
            : c
        ),
      };
    });

    // 仅 user 消息需要前端 POST 持久化 (与后端 SSE 兜底形成双保险, 5s 幂等去重)
    // assistant 消息由后端 rag_service.stream_chat 收尾时主动持久化, 前端无需调用
    // (修复 BUG-3: 早期版本前端 fire-and-forget POST assistant 消息易丢失)
    if (msg.role === "user") {
      try {
        await addSessionMessage(activeId, msg.role, msg.content);
      } catch (err) {
        console.error("[conversation] addSessionMessage failed:", err);
      }
      // Auto-title from first user message (后端 chat.py 也会 auto_title, 这里做前端 UI 同步)
      const conv = get().conversations.find((c) => c.id === activeId);
      if (conv && conv.title === "新对话") {
        const title = msg.content.slice(0, 30) + (msg.content.length > 30 ? "..." : "");
        get().renameOne(activeId, title).catch(() => {});
      }
    }
  },

  updateLastAssistant: (content, targetSessionId) => {
    // ✅ BUG 修复: 优先使用 targetSessionId (发送时捕获的会话 ID),
    // 而不是 get().activeId (用户切换会话后会变化).
    // 这样流式响应期间用户切换到其他会话, token 仍写入原会话, 不会串台.
    const id = targetSessionId ?? get().activeId;
    if (!id) return;
    set((s) => ({
      conversations: s.conversations.map((c) => {
        if (c.id !== id) return c;
        const msgs = [...c.messages];
        const last = msgs[msgs.length - 1];
        if (last?.role === "assistant") {
          msgs[msgs.length - 1] = { ...last, content };
        } else {
          msgs.push({ role: "assistant", content });
        }
        return { ...c, messages: msgs };
      }),
    }));
  },

  setThinking: (content, targetSessionId) => {
    // ✅ 同 updateLastAssistant, 绑定到发送时的会话
    const id = targetSessionId ?? get().activeId;
    if (!id) return;
    set((s) => ({
      conversations: s.conversations.map((c) => {
        if (c.id !== id) return c;
        const msgs = [...c.messages];
        const last = msgs[msgs.length - 1];
        if (last?.role === "assistant") {
          msgs[msgs.length - 1] = { ...last, thinking: content };
        }
        return { ...c, messages: msgs };
      }),
    }));
  },

  setStreaming: (v, targetSessionId) => {
    // ✅ 流式开始时记录 streamingSessionId, 结束时清除.
    // UI 用 (isStreaming && streamingSessionId === activeId) 判断是否显示进度.
    if (v) {
      const id = targetSessionId ?? get().activeId;
      set({ isStreaming: true, streamingSessionId: id });
    } else {
      // 只允许结束自己会话的流式状态, 避免被其他会话的 setStreaming(false) 误清
      const current = get().streamingSessionId;
      if (!targetSessionId || !current || current === targetSessionId) {
        set({ isStreaming: false, streamingSessionId: null });
      }
    }
  },
  setWebSearch: (v) => set({ webSearch: v }),
  setMcpTools: (v) => set({ mcpTools: v }),

  addProgressStep: (step, targetSessionId) => {
    // ✅ 只更新属于 targetSessionId 的进度, 避免切换会话后进度串台
    const current = get().streamingSessionId;
    if (targetSessionId && current !== targetSessionId) return;
    set((s) => ({ liveProgress: [...s.liveProgress, step] }));
  },

  updateLastProgressStep: (update, targetSessionId) => {
    const current = get().streamingSessionId;
    if (targetSessionId && current !== targetSessionId) return;
    set((s) => {
      const steps = [...s.liveProgress];
      if (steps.length > 0) {
        steps[steps.length - 1] = { ...steps[steps.length - 1], ...update };
      }
      return { liveProgress: steps };
    });
  },

  setLiveCitations: (citations, targetSessionId) => {
    const current = get().streamingSessionId;
    if (targetSessionId && current !== targetSessionId) return;
    set({ liveCitations: citations });
  },

  setProgressPhase: (v, targetSessionId) => {
    const current = get().streamingSessionId;
    if (targetSessionId && current !== targetSessionId) return;
    set({ progressPhase: v });
  },

  markAllProgressDone: (targetSessionId) => {
    const current = get().streamingSessionId;
    if (targetSessionId && current !== targetSessionId) return;
    set((s) => ({
      progressPhase: false,
      liveProgress: s.liveProgress.map((step) =>
        step.status === "running" ? { ...step, status: "done" as const } : step
      ),
    }));
  },

  clearLiveState: (_targetSessionId) => {
    // clearLiveState 通常在发送前调用, 此时 streamingSessionId 还没设,
    // 不做 targetSessionId 检查, 直接清空. 参数保留是为了 API 一致性.
    void _targetSessionId;
    set({ liveProgress: [], liveCitations: [], progressPhase: true });
  },

  activeConversation: () => {
    const { conversations, activeId } = get();
    return conversations.find((c) => c.id === activeId) || null;
  },
}));
