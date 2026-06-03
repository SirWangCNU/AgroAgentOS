import { create } from "zustand";

interface Toast {
  id: number;
  message: string;
  type: "success" | "error" | "info";
}

interface UIState {
  sidebarCollapsed: boolean;
  searchOpen: boolean;
  toasts: Toast[];
  toggleSidebar: () => void;
  setSearchOpen: (open: boolean) => void;
  showToast: (message: string, type?: Toast["type"]) => void;
  removeToast: (id: number) => void;
}

let toastId = 0;

export const useUIStore = create<UIState>((set) => ({
  sidebarCollapsed: true,
  searchOpen: false,
  toasts: [],

  toggleSidebar: () =>
    set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),

  setSearchOpen: (open) => set({ searchOpen: open }),

  showToast: (message, type = "info") => {
    const id = ++toastId;
    set((s) => ({ toasts: [...s.toasts, { id, message, type }] }));
    setTimeout(() => {
      set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) }));
    }, 3000);
  },

  removeToast: (id) =>
    set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),
}));
