import { create } from "zustand";
import type { ChatMessage, Citation } from "../types/chat";
import type { ProgressStep } from "../components/chat/ProgressSteps";
import {
  createSession,
  listSessions,
  deleteSession,
  updateSession,
  getSession,
  addSessionMessage,
  type SessionOut,
} from "../api/sessions";

interface Conversation extends SessionOut {
  messages: ChatMessage[];
}

interface ConversationState {
  conversations: Conversation[];
  activeId: string | null;
  isStreaming: boolean;
  isLoadingMessages: boolean;

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
  addMessage: (msg: ChatMessage) => Promise<void>;
  updateLastAssistant: (content: string) => void;
  setThinking: (content: string) => void;
  setStreaming: (v: boolean) => void;
  setWebSearch: (v: boolean) => void;
  setMcpTools: (v: boolean) => void;

  // Progress tracking
  addProgressStep: (step: ProgressStep) => void;
  updateLastProgressStep: (step: Partial<ProgressStep>) => void;
  setLiveCitations: (citations: Citation[]) => void;
  setProgressPhase: (v: boolean) => void;
  markAllProgressDone: () => void;
  clearLiveState: () => void;

  // Getters
  activeConversation: () => Conversation | null;
}

export const useConversationStore = create<ConversationState>((set, get) => ({
  conversations: [],
  activeId: null,
  isStreaming: false,
  isLoadingMessages: false,
  webSearch: false,
  mcpTools: true,
  liveProgress: [],
  liveCitations: [],
  progressPhase: true,

  loadConversations: async () => {
    try {
      const sessions = await listSessions();
      set({
        conversations: sessions.map((s) => ({ ...s, messages: [] })),
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
    const conv: Conversation = { ...session, messages: [] };
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
      const detail = await getSession(id);
      const messages: ChatMessage[] = detail.messages.map((m) => ({
        role: m.role as "user" | "assistant",
        content: m.content,
        ...(m.image_url ? { imageUrl: m.image_url } : {}),
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
              c.id === id ? { ...c, messages: merged, title: detail.title } : c
            ),
          };
        }
        // Conversation not in store (e.g. direct URL navigation) — add it
        return {
          isLoadingMessages: false,
          conversations: [
            {
              id: detail.id,
              title: detail.title,
              created_at: detail.created_at,
              updated_at: detail.updated_at,
              message_count: detail.messages.length,
              messages,
            },
            ...s.conversations,
          ],
        };
      });
    } catch (err) {
      console.error("Failed to load messages:", err);
      set({ isLoadingMessages: false });
      throw err; // Re-throw so the caller can handle the error
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
    // Persist to backend —— 必须 await
    // 之前用 fire-and-forget 模式发出 POST，紧接着 chatStream 占用 HTTP 连接池，
    // 导致 user 消息的 POST 偶发被 abort/丢弃，DB 里只有 assistant 消息没有 user 消息
    try {
      await addSessionMessage(activeId, msg.role, msg.content);
    } catch (err) {
      console.error("[conversation] addSessionMessage failed:", err);
    }
    // Auto-title from first user message
    if (msg.role === "user") {
      const conv = get().conversations.find((c) => c.id === activeId);
      if (conv && conv.title === "新对话") {
        const title = msg.content.slice(0, 30) + (msg.content.length > 30 ? "..." : "");
        get().renameOne(activeId, title).catch(() => {});
      }
    }
  },

  updateLastAssistant: (content) => {
    const { activeId } = get();
    if (!activeId) return;
    set((s) => ({
      conversations: s.conversations.map((c) => {
        if (c.id !== activeId) return c;
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

  setThinking: (content) => {
    const { activeId } = get();
    if (!activeId) return;
    set((s) => ({
      conversations: s.conversations.map((c) => {
        if (c.id !== activeId) return c;
        const msgs = [...c.messages];
        const last = msgs[msgs.length - 1];
        if (last?.role === "assistant") {
          msgs[msgs.length - 1] = { ...last, thinking: content };
        }
        return { ...c, messages: msgs };
      }),
    }));
  },

  setStreaming: (v) => set({ isStreaming: v }),
  setWebSearch: (v) => set({ webSearch: v }),
  setMcpTools: (v) => set({ mcpTools: v }),

  addProgressStep: (step) => {
    set((s) => ({ liveProgress: [...s.liveProgress, step] }));
  },

  updateLastProgressStep: (update) => {
    set((s) => {
      const steps = [...s.liveProgress];
      if (steps.length > 0) {
        steps[steps.length - 1] = { ...steps[steps.length - 1], ...update };
      }
      return { liveProgress: steps };
    });
  },

  setLiveCitations: (citations) => set({ liveCitations: citations }),

  setProgressPhase: (v) => set({ progressPhase: v }),

  markAllProgressDone: () => {
    set((s) => ({
      progressPhase: false,
      liveProgress: s.liveProgress.map((step) =>
        step.status === "running" ? { ...step, status: "done" as const } : step
      ),
    }));
  },

  clearLiveState: () => set({ liveProgress: [], liveCitations: [], progressPhase: true }),

  activeConversation: () => {
    const { conversations, activeId } = get();
    return conversations.find((c) => c.id === activeId) || null;
  },
}));
