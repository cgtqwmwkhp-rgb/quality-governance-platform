/**
 * Global axios loading is opt-in only.
 *
 * Historically every API call toggled useAppStore.isLoading, which flashed a
 * global UI busy state on navigation and background polls. Pages already own
 * local loading; callers that truly need a global indicator must pass
 * `{ globalLoading: true }` on the axios config.
 */

export type GlobalLoadingConfig = {
  globalLoading?: boolean
}

export function shouldTrackGlobalLoading(config?: GlobalLoadingConfig | null): boolean {
  return config?.globalLoading === true
}

/** Increment tracked in-flight count; set loading true when first tracked request starts. */
export function beginGlobalLoading(
  activeTracked: number,
  track: boolean,
  setLoading: (loading: boolean) => void,
): number {
  if (!track) return activeTracked
  const next = activeTracked + 1
  if (next === 1) setLoading(true)
  return next
}

/** Decrement tracked in-flight count; clear loading when last tracked request ends. */
export function endGlobalLoading(
  activeTracked: number,
  track: boolean,
  setLoading: (loading: boolean) => void,
): number {
  if (!track) return activeTracked
  const next = Math.max(0, activeTracked - 1)
  if (next === 0) setLoading(false)
  return next
}
