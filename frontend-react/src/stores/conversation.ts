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
  addMessage: (msg: ChatMessage) => void;
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
        // Merge: keep already-loaded messages for existing conversations
        const msgMap = new Map(s.conversations.map((c) => [c.id, c.messages]));
        return {
          conversations: sessions.map((session) => ({
            ...session,
            messages: msgMap.get(session.id) || [],
          })),
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
        const exists = s.conversations.some((c) => c.id === id);
        if (exists) {
          // Update existing conversation
          return {
            isLoadingMessages: false,
            conversations: s.conversations.map((c) =>
              c.id === id ? { ...c, messages, title: detail.title } : c
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

  addMessage: (msg) => {
    const { activeId } = get();
    if (!activeId) return;
    set((s) => ({
      conversations: s.conversations.map((c) =>
        c.id === activeId
          ? { ...c, messages: [...c.messages, msg] }
          : c
      ),
    }));
    // Persist to backend
    addSessionMessage(activeId, msg.role, msg.content).catch(() => {});
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
