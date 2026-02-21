import { create } from "zustand";
import { persist } from "zustand/middleware";

interface AppState {
  // Transient state (not persisted)
  isLoading: boolean;
  isOnline: boolean;
  connectionStatus: "connected" | "disconnected" | "reconnecting";
  setLoading: (loading: boolean) => void;
  setOnline: (online: boolean) => void;
  setConnectionStatus: (
    status: "connected" | "disconnected" | "reconnecting",
  ) => void;

  // Persisted user preferences
  sidebarOpen: boolean;
  theme: "light" | "dark" | "system";
  setSidebarOpen: (open: boolean) => void;
  toggleSidebar: () => void;
  setTheme: (theme: "light" | "dark" | "system") => void;
}

export const useAppStore = create<AppState>()(
  persist(
    (set) => ({
      isLoading: false,
      isOnline: typeof navigator !== "undefined" ? navigator.onLine : true,
      connectionStatus: "connected",

      setLoading: (loading) => set({ isLoading: loading }),
      setOnline: (online) => set({ isOnline: online }),
      setConnectionStatus: (status) => set({ connectionStatus: status }),

      sidebarOpen: true,
      theme: "system",
      setSidebarOpen: (open) => set({ sidebarOpen: open }),
      toggleSidebar: () =>
        set((state) => ({ sidebarOpen: !state.sidebarOpen })),
      setTheme: (theme) => set({ theme }),
    }),
    {
      name: "app-preferences",
      partialize: (state) => ({
        theme: state.theme,
        sidebarOpen: state.sidebarOpen,
      }),
    },
  ),
);

// Selectors for optimized re-renders
export const selectIsLoading = (state: AppState) => state.isLoading;
export const selectIsOnline = (state: AppState) => state.isOnline;
export const selectConnectionStatus = (state: AppState) =>
  state.connectionStatus;
export const selectSidebarOpen = (state: AppState) => state.sidebarOpen;
export const selectTheme = (state: AppState) => state.theme;
