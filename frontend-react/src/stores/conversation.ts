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

  // Chat settings
  webSearch: boolean;
  mcpTools: boolean;

  // Live streaming state
  liveProgress: ProgressStep[];
  liveCitations: Citation[];
  progressPhase: boolean; // true = still in retrieval/search phase

  // Actions
  loadConversations: () => Promise<void>;
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
    } catch {
      // silently fail
    }
  },

  createNew: async () => {
    const session = await createSession();
    const conv: Conversation = { ...session, messages: [] };
    set((s) => ({
      conversations: [conv, ...s.conversations],
      activeId: conv.id,
    }));
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
    const detail = await getSession(id);
    const messages: ChatMessage[] = detail.messages.map((m) => ({
      role: m.role as "user" | "assistant",
      content: m.content,
    }));
    set((s) => ({
      conversations: s.conversations.map((c) =>
        c.id === id ? { ...c, messages } : c
      ),
    }));
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
