import { create } from "zustand";
import type { User } from "../types/api";
import { STORAGE_KEYS } from "../lib/constants";

interface AuthState {
  user: User | null;
  token: string | null;
  login: (token: string, user: User) => void;
  logout: () => void;
  isAdmin: () => boolean;
}

export const useAuthStore = create<AuthState>((set, get) => ({
  user: JSON.parse(localStorage.getItem(STORAGE_KEYS.USER) || "null"),
  token: localStorage.getItem(STORAGE_KEYS.TOKEN),

  login: (token, user) => {
    localStorage.setItem(STORAGE_KEYS.TOKEN, token);
    localStorage.setItem(STORAGE_KEYS.USER, JSON.stringify(user));
    set({ token, user });
  },

  logout: () => {
    localStorage.removeItem(STORAGE_KEYS.TOKEN);
    localStorage.removeItem(STORAGE_KEYS.USER);
    set({ token: null, user: null });
    window.location.href = "/login";
  },

  isAdmin: () => get().user?.role === "admin",
}));
