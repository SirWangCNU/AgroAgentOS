import { create } from "zustand";
import type { HealthData, Skill } from "../types/api";

interface HealthState {
  health: HealthData | null;
  skills: Skill[];
  setHealth: (data: HealthData) => void;
  setSkills: (skills: Skill[]) => void;
}

export const useHealthStore = create<HealthState>((set) => ({
  health: null,
  skills: [],
  setHealth: (data) => set({ health: data }),
  setSkills: (skills) => set({ skills }),
}));
