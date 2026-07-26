import { type ReactNode } from 'react'
import { Clock } from 'lucide-react'
import { Button } from '../Button'
import { Skeleton } from '../SkeletonLoader'
import { ErrorState } from './ErrorState'
import { DEFAULT_STALL_MS, resolveAsyncStatus, useLoadingStall } from './asyncStatus'

export interface AsyncStateProps {
  loading?: boolean
  /** Failure message, or `null` when the last load succeeded. */
  error?: string | null
  /** True when the load succeeded and returned nothing. */
  isEmpty?: boolean
  /** Re-runs the load. Drives both the error retry and the stalled-load escape. */
  onRetry?: () => void

  /** Shown while loading. Pass the skeleton that matches the real layout. */
  loadingFallback?: ReactNode

  errorTitle?: ReactNode
  errorDescription?: ReactNode
  retryLabel?: ReactNode

  /**
   * Shown only when the load succeeded and returned nothing. Omit it and an
   * empty result falls through to `children` rather than blanking the page.
   */
  empty?: ReactNode

  /**
   * How long a load may run before the user is told it is taking longer than
   * expected. 0 disables the guard.
   */
  stallAfterMs?: number
  stalledMessage?: ReactNode

  children?: ReactNode
  'data-testid'?: string
}

/**
 * The four states every data-backed surface has, in one place.
 *
 * Renders exactly one of loading / error / empty / data, in that precedence,
 * so a failed request can never be presented as "no records" and a hung
 * request can never leave a skeleton on screen with no way out.
 *
 * Only the loading branch introduces a wrapper element; the empty and data
 * branches render their children unwrapped so this can sit inside tables and
 * grids without disturbing layout.
 */
export function AsyncState({
  loading = false,
  error,
  isEmpty = false,
  onRetry,
  loadingFallback,
  errorTitle,
  errorDescription,
  retryLabel,
  empty,
  stallAfterMs = DEFAULT_STALL_MS,
  stalledMessage = 'This is taking longer than expected. The server may not be responding.',
  children,
  'data-testid': testId = 'async-state',
}: AsyncStateProps) {
  const status = resolveAsyncStatus({ loading, error, isEmpty })
  const stalled = useLoadingStall(status === 'loading', stallAfterMs)

  if (status === 'loading') {
    return (
      <div data-testid={testId} data-async-status="loading">
        {loadingFallback ?? <Skeleton lines={4} />}
        {stalled ? (
          <div
            role="status"
            aria-live="polite"
            data-testid={`${testId}-stalled`}
            className="mt-4 flex flex-col gap-3 rounded-xl border border-warning/30 bg-warning/5 p-4 sm:flex-row sm:items-center sm:justify-between"
          >
            <div className="flex min-w-0 gap-3">
              <Clock className="mt-0.5 h-5 w-5 shrink-0 text-warning" aria-hidden="true" />
              <p className="text-sm text-foreground">{stalledMessage}</p>
            </div>
            {onRetry ? (
              <Button
                variant="outline"
                onClick={onRetry}
                data-testid={`${testId}-stalled-retry`}
              >
                {retryLabel ?? 'Try again'}
              </Button>
            ) : null}
          </div>
        ) : null}
      </div>
    )
  }

  if (status === 'error') {
    return (
      <ErrorState
        title={errorTitle}
        description={errorDescription}
        message={error || undefined}
        onRetry={onRetry}
        retryLabel={retryLabel}
        data-testid={`${testId}-error`}
      />
    )
  }

  if (status === 'empty' && empty !== undefined) {
    return <>{empty}</>
  }

  return <>{children}</>
}
