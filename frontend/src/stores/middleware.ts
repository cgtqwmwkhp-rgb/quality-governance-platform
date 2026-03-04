import { devtools, persist } from "zustand/middleware";
import type { StateCreator } from "zustand";

export function withDevtools<T>(
  name: string,
  fn: StateCreator<T>,
): StateCreator<T> {
  if (process.env.NODE_ENV === "development") {
    return devtools(fn, { name }) as StateCreator<T>;
  }
  return fn;
}

export function withPersist<T>(
  name: string,
  fn: StateCreator<T>,
  partialize?: (state: T) => Partial<T>,
): StateCreator<T> {
  return persist(fn, { name, partialize }) as unknown as StateCreator<T>;
}
