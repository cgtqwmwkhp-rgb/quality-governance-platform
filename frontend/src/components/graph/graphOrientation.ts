/**
 * Shared V/H orientation swap primitive (X-2).
 *
 * One toggle family for Doc Graph maps / spines and (later) Job Lifecycle
 * Matrix · Transpose · Phase. Layout application stays surface-specific;
 * this module owns the orientation vocabulary only.
 */

export type GraphOrientation = 'horizontal' | 'vertical'

export const GRAPH_ORIENTATIONS: readonly GraphOrientation[] = [
  'horizontal',
  'vertical',
] as const

export const DEFAULT_GRAPH_ORIENTATION: GraphOrientation = 'horizontal'

export function isGraphOrientation(value: unknown): value is GraphOrientation {
  return value === 'horizontal' || value === 'vertical'
}

export function resolveGraphOrientation(
  preferred: unknown,
  fallback: GraphOrientation = DEFAULT_GRAPH_ORIENTATION,
): GraphOrientation {
  return isGraphOrientation(preferred) ? preferred : fallback
}

export function toggleGraphOrientation(current: GraphOrientation): GraphOrientation {
  return current === 'horizontal' ? 'vertical' : 'horizontal'
}

export function graphOrientationLabel(orientation: GraphOrientation): string {
  return orientation === 'horizontal' ? 'Horizontal' : 'Vertical'
}

export function graphOrientationStorageKey(surface: string): string {
  return `graph_orientation_${surface}`
}

export function parseStoredGraphOrientation(raw: string | null | undefined): GraphOrientation | null {
  return isGraphOrientation(raw) ? raw : null
}

export function readStoredGraphOrientation(
  surface: string,
  storage: Pick<Storage, 'getItem'> | null | undefined = typeof localStorage !== 'undefined'
    ? localStorage
    : null,
): GraphOrientation | null {
  if (!storage) return null
  try {
    return parseStoredGraphOrientation(storage.getItem(graphOrientationStorageKey(surface)))
  } catch {
    return null
  }
}

export function writeStoredGraphOrientation(
  surface: string,
  orientation: GraphOrientation,
  storage: Pick<Storage, 'setItem'> | null | undefined = typeof localStorage !== 'undefined'
    ? localStorage
    : null,
): void {
  if (!storage) return
  try {
    storage.setItem(graphOrientationStorageKey(surface), orientation)
  } catch {
    // Storage may be unavailable (private mode / SSR) — ignore.
  }
}
