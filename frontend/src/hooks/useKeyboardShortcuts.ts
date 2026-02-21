import { useEffect, useRef } from "react";

interface Shortcut {
  key: string;
  modifiers?: ("ctrl" | "meta" | "shift" | "alt")[];
  description: string;
  action: () => void;
  scope?: string;
}

const globalRegistry: Map<string, Shortcut> = new Map();

function getShortcutId(shortcut: Pick<Shortcut, "key" | "modifiers">): string {
  const mods = (shortcut.modifiers || []).sort().join("+");
  return mods
    ? `${mods}+${shortcut.key.toLowerCase()}`
    : shortcut.key.toLowerCase();
}

export function getRegisteredShortcuts(): Shortcut[] {
  return Array.from(globalRegistry.values());
}

export function useKeyboardShortcuts(shortcuts: Shortcut[]) {
  const shortcutsRef = useRef(shortcuts);
  shortcutsRef.current = shortcuts;

  useEffect(() => {
    for (const s of shortcutsRef.current) {
      globalRegistry.set(getShortcutId(s), s);
    }

    const handler = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement;
      const isInput =
        ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName) ||
        target.isContentEditable;

      for (const s of shortcutsRef.current) {
        const mods = s.modifiers || [];
        const needsCtrl = mods.includes("ctrl");
        const needsMeta = mods.includes("meta");
        const needsShift = mods.includes("shift");
        const needsAlt = mods.includes("alt");

        if (isInput && mods.length === 0) continue;

        if (
          e.key.toLowerCase() === s.key.toLowerCase() &&
          (needsCtrl ? e.ctrlKey : !e.ctrlKey || needsMeta) &&
          (needsMeta ? e.metaKey : !e.metaKey || needsCtrl) &&
          (needsShift ? e.shiftKey : !e.shiftKey) &&
          (needsAlt ? e.altKey : !e.altKey)
        ) {
          e.preventDefault();
          s.action();
          return;
        }
      }
    };

    window.addEventListener("keydown", handler);
    return () => {
      window.removeEventListener("keydown", handler);
      for (const s of shortcutsRef.current) {
        globalRegistry.delete(getShortcutId(s));
      }
    };
  }, []);
}

export type { Shortcut };
