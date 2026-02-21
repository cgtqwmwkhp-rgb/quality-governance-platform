import { create } from 'zustand';

interface AppState {
  isLoading: boolean;
  isOnline: boolean;
  connectionStatus: 'connected' | 'disconnected' | 'reconnecting';
  setLoading: (loading: boolean) => void;
  setOnline: (online: boolean) => void;
  setConnectionStatus: (status: 'connected' | 'disconnected' | 'reconnecting') => void;
}

export const useAppStore = create<AppState>((set) => ({
  isLoading: false,
  isOnline: navigator.onLine,
  connectionStatus: 'connected',

  setLoading: (loading) => set({ isLoading: loading }),
  setOnline: (online) => set({ isOnline: online }),
  setConnectionStatus: (status) => set({ connectionStatus: status }),
}));

if (typeof window !== 'undefined') {
  window.addEventListener('online', () => useAppStore.getState().setOnline(true));
  window.addEventListener('offline', () => useAppStore.getState().setOnline(false));
}
