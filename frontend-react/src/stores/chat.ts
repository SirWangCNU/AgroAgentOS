import { create } from "zustand";
import type { ChatMessage, Citation, ProgressEvent } from "../types/chat";

interface ChatState {
  webEnabled: boolean;
  mcpEnabled: boolean;
  messages: ChatMessage[];
  activeCtxTab: "detail" | "tools" | "stats";
  citations: Citation[];
  progressEvents: ProgressEvent[];
  toggleWeb: () => void;
  toggleMcp: () => void;
  addMessage: (msg: ChatMessage) => void;
  updateLastAssistant: (content: string) => void;
  setThinking: (content: string) => void;
  setCitations: (citations: Citation[]) => void;
  addProgress: (event: ProgressEvent) => void;
  setCtxTab: (tab: "detail" | "tools" | "stats") => void;
  clearMessages: () => void;
}

export const useChatStore = create<ChatState>((set) => ({
  webEnabled: false,
  mcpEnabled: true,
  messages: [],
  activeCtxTab: "detail",
  citations: [],
  progressEvents: [],

  toggleWeb: () => set((s) => ({ webEnabled: !s.webEnabled })),
  toggleMcp: () => set((s) => ({ mcpEnabled: !s.mcpEnabled })),

  addMessage: (msg) => set((s) => ({ messages: [...s.messages, msg] })),

  updateLastAssistant: (content) =>
    set((s) => {
      const msgs = [...s.messages];
      const last = msgs[msgs.length - 1];
      if (last?.role === "assistant") {
        msgs[msgs.length - 1] = { ...last, content };
      } else {
        msgs.push({ role: "assistant", content });
      }
      return { messages: msgs };
    }),

  setThinking: (content) =>
    set((s) => {
      const msgs = [...s.messages];
      const last = msgs[msgs.length - 1];
      if (last?.role === "assistant") {
        msgs[msgs.length - 1] = { ...last, thinking: content };
      }
      return { messages: msgs };
    }),

  setCitations: (citations) => set({ citations }),
  addProgress: (event) =>
    set((s) => ({ progressEvents: [...s.progressEvents, event] })),
  setCtxTab: (tab) => set({ activeCtxTab: tab }),
  clearMessages: () => set({ messages: [], citations: [], progressEvents: [] }),
}));
