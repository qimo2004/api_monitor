import { create } from 'zustand';

interface AlertState {
  pendingCount: number;
  setPendingCount: (count: number) => void;
  // 刷新触发器：每次调用 bump 一次，通知铃铛重新拉取列表
  refreshTrigger: number;
  triggerRefresh: () => void;
}

export const useAlertStore = create<AlertState>((set) => ({
  pendingCount: 0,
  setPendingCount: (count) => set({ pendingCount: count }),
  refreshTrigger: 0,
  triggerRefresh: () => set((s) => ({ refreshTrigger: s.refreshTrigger + 1 })),
}));
