import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface PreferencesState {
  sidebarCollapsed: boolean;
  tablePageSize: number;
  savedFilters: Record<string, Record<string, string>>;
  toggleSidebar: () => void;
  setSidebarCollapsed: (collapsed: boolean) => void;
  setTablePageSize: (size: number) => void;
  saveFilter: (page: string, filters: Record<string, string>) => void;
  clearFilter: (page: string) => void;
}

export const usePreferencesStore = create<PreferencesState>()(
  persist(
    (set) => ({
      sidebarCollapsed: false,
      tablePageSize: 20,
      savedFilters: {},

      toggleSidebar: () =>
        set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),

      setSidebarCollapsed: (collapsed) =>
        set({ sidebarCollapsed: collapsed }),

      setTablePageSize: (size) =>
        set({ tablePageSize: size }),

      saveFilter: (page, filters) =>
        set((state) => ({
          savedFilters: { ...state.savedFilters, [page]: filters },
        })),

      clearFilter: (page) =>
        set((state) => {
          const { [page]: _, ...rest } = state.savedFilters;
          return { savedFilters: rest };
        }),
    }),
    {
      name: 'qgp-preferences',
    }
  )
);
