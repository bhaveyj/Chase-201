import { create } from "zustand";
import type { LegacyStrategy, Strategy, V2Strategy } from "./api";

// Deliberately no persistence middleware: only unsaved UI choices belong here.
type UIState = {
  activeSlot: number;
  draftId: string | null;
  pendingOrder: string[] | null;
  strategy: Strategy;
  v2Strategy: V2Strategy;
  setV2Strategy: (strategy: V2Strategy) => void;
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
  v2Strategy: "BALANCED",
  setV2Strategy: (v2Strategy) => set({ v2Strategy }),
  legacyStrategy: { intent: "ROTATE", riskFocus: "BALANCED" },
  setActiveSlot: (activeSlot) => set({ activeSlot }),
  editOrder: (draftId, pendingOrder) => set({ draftId, pendingOrder }),
  setStrategy: (strategy) => set({ strategy }),
  setLegacyStrategy: (next) =>
    set((s) => ({ legacyStrategy: { ...s.legacyStrategy, ...next } })),
}));
