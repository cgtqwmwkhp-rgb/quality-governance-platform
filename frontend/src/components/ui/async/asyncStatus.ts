import { useEffect, useState } from 'react'

export type AsyncStatus = 'loading' | 'error' | 'empty' | 'ready'

export interface AsyncStatusInput {
  loading?: boolean
  /**
   * Human-readable failure message, or `null`/`undefined` when the last load
   * succeeded. An empty string still counts as a failure, so a blank message
   * can never be mistaken for success.
   */
  error?: string | null
  /** True when the load succeeded and returned no rows. */
  isEmpty?: boolean
}

/**
 * The single ordering every surface must obey: loading, then error, then
 * empty, then data.
 *
 * Error outranks empty. A register that renders "no records" after the API
 * failed is telling the user the records do not exist (PX-181, PX-170), which
 * is worse than telling them nothing at all.
 */
export function resolveAsyncStatus({
  loading = false,
  error,
  isEmpty = false,
}: AsyncStatusInput): AsyncStatus {
  if (loading) return 'loading'
  if (error !== null && error !== undefined) return 'error'
  if (isEmpty) return 'empty'
  return 'ready'
}

/** A load running longer than this is reported to the user as stalled. */
export const DEFAULT_STALL_MS = 15000

/**
 * True once `active` has been continuously true for `afterMs`.
 *
 * A skeleton with no time limit is indistinguishable from a dead page: a
 * request that hangs and never settles leaves the loading flag set forever
 * and the user with nothing to read and nothing to click (PX-170). Passing
 * `afterMs = 0` disables the guard.
 */
export function useLoadingStall(active: boolean, afterMs: number = DEFAULT_STALL_MS): boolean {
  const [stalled, setStalled] = useState(false)

  useEffect(() => {
    setStalled(false)
    if (!active || afterMs <= 0) return
    const timer = window.setTimeout(() => setStalled(true), afterMs)
    return () => window.clearTimeout(timer)
  }, [active, afterMs])

  return stalled
}
