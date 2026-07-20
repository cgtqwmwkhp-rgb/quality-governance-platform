import { useEffect, useRef } from 'react'

interface Shortcut {
  key: string
  modifiers?: ('ctrl' | 'meta' | 'shift' | 'alt')[]
  description: string
  action: () => void
  scope?: string
}

const globalRegistry: Map<string, Shortcut> = new Map()

function getShortcutId(shortcut: Pick<Shortcut, 'key' | 'modifiers'>): string {
  const mods = (shortcut.modifiers || []).sort().join('+')
  return mods ? `${mods}+${shortcut.key.toLowerCase()}` : shortcut.key.toLowerCase()
}

export function getRegisteredShortcuts(): Shortcut[] {
  return Array.from(globalRegistry.values())
}

const EDITABLE_ROLES = new Set(['combobox', 'listbox', 'searchbox'])

function isEditableTarget(el: EventTarget | null): boolean {
  let node = el instanceof HTMLElement ? el : null
  while (node) {
    if (['INPUT', 'TEXTAREA', 'SELECT'].includes(node.tagName)) return true
    if (node.isContentEditable) return true
    const role = node.getAttribute('role')
    if (role && EDITABLE_ROLES.has(role)) return true
    node = node.parentElement
  }
  return false
}

function hasPrimaryModifier(modifiers: Shortcut['modifiers']): boolean {
  return (modifiers || []).some((m) => m === 'ctrl' || m === 'meta' || m === 'alt')
}

export function useKeyboardShortcuts(shortcuts: Shortcut[]) {
  const shortcutsRef = useRef(shortcuts)
  shortcutsRef.current = shortcuts

  useEffect(() => {
    for (const s of shortcutsRef.current) {
      globalRegistry.set(getShortcutId(s), s)
    }

    const handler = (e: KeyboardEvent) => {
      const isEditable = isEditableTarget(e.target)

      for (const s of shortcutsRef.current) {
        const mods = s.modifiers || []
        const needsCtrl = mods.includes('ctrl')
        const needsMeta = mods.includes('meta')
        const needsShift = mods.includes('shift')
        const needsAlt = mods.includes('alt')

        if (isEditable && !hasPrimaryModifier(mods)) continue

        if (
          e.key.toLowerCase() === s.key.toLowerCase() &&
          (needsCtrl ? e.ctrlKey : !e.ctrlKey || needsMeta) &&
          (needsMeta ? e.metaKey : !e.metaKey || needsCtrl) &&
          (needsShift ? e.shiftKey : !e.shiftKey) &&
          (needsAlt ? e.altKey : !e.altKey)
        ) {
          e.preventDefault()
          s.action()
          return
        }
      }
    }

    window.addEventListener('keydown', handler)
    return () => {
      window.removeEventListener('keydown', handler)
      for (const s of shortcutsRef.current) {
        globalRegistry.delete(getShortcutId(s))
      }
    }
  }, [])
}

export type { Shortcut }
