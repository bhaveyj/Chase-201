import { create } from "zustand";
import type { Strategy } from "./api";

// Deliberately no persistence middleware: only unsaved UI choices belong here.
type UIState = {
  activeSlot: number;
  draftId: string | null;
  pendingOrder: string[] | null;
  strategy: Strategy;
  setActiveSlot: (slot: number) => void;
  editOrder: (draftId: string, order: string[]) => void;
  setStrategy: (strategy: Partial<Strategy>) => void;
};
export const useUI = create<UIState>((set) => ({
  activeSlot: 0,
  draftId: null,
  pendingOrder: null,
  strategy: { intent: "ROTATE", riskFocus: "BALANCED" },
  setActiveSlot: (activeSlot) => set({ activeSlot }),
  editOrder: (draftId, pendingOrder) => set({ draftId, pendingOrder }),
  setStrategy: (next) => set((s) => ({ strategy: { ...s.strategy, ...next } })),
}));
