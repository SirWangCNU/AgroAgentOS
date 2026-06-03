import { create } from "zustand";
import type { ChatMessage } from "../types/chat";
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

  // Getters
  activeConversation: () => Conversation | null;
}

export const useConversationStore = create<ConversationState>((set, get) => ({
  conversations: [],
  activeId: null,
  isStreaming: false,

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

  activeConversation: () => {
    const { conversations, activeId } = get();
    return conversations.find((c) => c.id === activeId) || null;
  },
}));
