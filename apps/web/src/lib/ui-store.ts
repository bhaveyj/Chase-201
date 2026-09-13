import { create } from "zustand";
import type { LegacyStrategy, Strategy } from "./api";

// Deliberately no persistence middleware: only unsaved UI choices belong here.
type UIState = {
  activeSlot: number;
  draftId: string | null;
  pendingOrder: string[] | null;
  strategy: Strategy;
  legacyStrategy: LegacyStrategy;
  setActiveSlot: (slot: number) => void;
  editOrder: (draftId: string, order: string[]) => void;
  setStrategy: (strategy: Strategy) => void;
  setLegacyStrategy: (strategy: Partial<LegacyStrategy>) => void;
};
export const useUI = create<UIState>((set) => ({
  activeSlot: 0,
  draftId: null,
  pendingOrder: null,
  strategy: "BALANCED",
  legacyStrategy: { intent: "ROTATE", riskFocus: "BALANCED" },
  setActiveSlot: (activeSlot) => set({ activeSlot }),
  editOrder: (draftId, pendingOrder) => set({ draftId, pendingOrder }),
  setStrategy: (strategy) => set({ strategy }),
  setLegacyStrategy: (next) =>
    set((s) => ({ legacyStrategy: { ...s.legacyStrategy, ...next } })),
}));
