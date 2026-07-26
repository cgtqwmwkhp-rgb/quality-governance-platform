/**
 * Shared async-state primitive.
 *
 * One place that owns the four states every data-backed surface has —
 * loading, error, empty, data — and the precedence between them.
 *
 * The rule it exists to enforce: a surface may only claim there is nothing to
 * show when the request actually succeeded and returned nothing. A failed or
 * hung request gets a failure message and a retry control, never an empty
 * state and never an endless skeleton.
 *
 * Not exported from `components/ui/index.ts` yet — import from
 * `components/ui/async` directly, as `SetupRequiredPanel` already does.
 */

export { AsyncState } from './AsyncState'
export type { AsyncStateProps } from './AsyncState'
export { ErrorState } from './ErrorState'
export type { ErrorStateProps } from './ErrorState'
export { DEFAULT_STALL_MS, resolveAsyncStatus, useLoadingStall } from './asyncStatus'
export type { AsyncStatus, AsyncStatusInput } from './asyncStatus'
