import { create } from 'zustand';

interface AlertState {
  pendingCount: number;
  setPendingCount: (count: number) => void;
}

export const useAlertStore = create<AlertState>((set) => ({
  pendingCount: 0,
  setPendingCount: (count) => set({ pendingCount: count }),
}));
