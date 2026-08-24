/**
 * GraphCoach step type + flag / dismiss helpers (X-2).
 *
 * Per-surface copy lives under `coachSteps/`. Visibility is gated solely by
 * the X-0 programme flag `graph_coach` — do not invent a second flag here.
 */

import type { GraphCoachStep, GraphCoachSurface } from './coachSteps/types'

export type { GraphCoachStep, GraphCoachSurface }

export function shouldShowGraphCoach(graphCoachEnabled: boolean): boolean {
  return Boolean(graphCoachEnabled)
}

export function coachDismissStorageKey(surface: GraphCoachSurface): string {
  return `graph_coach_dismissed_${surface}`
}

export function isCoachDismissed(
  surface: GraphCoachSurface,
  storage: Pick<Storage, 'getItem'> | null | undefined = typeof localStorage !== 'undefined'
    ? localStorage
    : null,
): boolean {
  if (!storage) return false
  try {
    return storage.getItem(coachDismissStorageKey(surface)) === '1'
  } catch {
    return false
  }
}

export function dismissCoach(
  surface: GraphCoachSurface,
  storage: Pick<Storage, 'setItem'> | null | undefined = typeof localStorage !== 'undefined'
    ? localStorage
    : null,
): void {
  if (!storage) return
  try {
    storage.setItem(coachDismissStorageKey(surface), '1')
  } catch {
    // ignore
  }
}

export function resetCoach(
  surface: GraphCoachSurface,
  storage: Pick<Storage, 'removeItem'> | null | undefined = typeof localStorage !== 'undefined'
    ? localStorage
    : null,
): void {
  if (!storage) return
  try {
    storage.removeItem(coachDismissStorageKey(surface))
  } catch {
    // ignore
  }
}

export function clampCoachStepIndex(index: number, stepCount: number): number {
  if (stepCount <= 0) return 0
  if (!Number.isFinite(index)) return 0
  return Math.min(Math.max(Math.trunc(index), 0), stepCount - 1)
}

export function coachStepProgress(index: number, stepCount: number): number {
  if (stepCount <= 0) return 0
  const clamped = clampCoachStepIndex(index, stepCount)
  return Math.round(((clamped + 1) / stepCount) * 100)
}

export function shouldRenderCoachPanel(
  graphCoachEnabled: boolean,
  surface: GraphCoachSurface,
  storage?: Pick<Storage, 'getItem'> | null,
): boolean {
  if (!shouldShowGraphCoach(graphCoachEnabled)) return false
  return !isCoachDismissed(surface, storage)
}
