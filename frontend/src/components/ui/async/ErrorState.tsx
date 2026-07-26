import { type ReactNode } from 'react'
import { AlertTriangle, RefreshCw } from 'lucide-react'
import { Button } from '../Button'
import { cn } from '../../../helpers/utils'

export interface ErrorStateProps {
  /** What failed, in the user's terms — e.g. "Near misses unavailable". */
  title?: ReactNode
  /** What it means for them, and what to do next. */
  description?: ReactNode
  /** The message from the API layer. Shown verbatim so support can act on it. */
  message?: ReactNode
  onRetry?: () => void
  retryLabel?: ReactNode
  className?: string
  'data-testid'?: string
}

/**
 * Persistent, in-page failure panel with a retry control.
 *
 * Deliberately *not* a toast and *not* an empty state. A toast is gone ten
 * seconds later, and an empty state asserts that there is nothing to show —
 * a claim the page cannot make when the request never returned.
 */
export function ErrorState({
  title = 'Something went wrong',
  description,
  message,
  onRetry,
  retryLabel = 'Try again',
  className,
  'data-testid': testId = 'async-error-state',
}: ErrorStateProps) {
  return (
    <div
      role="alert"
      aria-live="assertive"
      data-testid={testId}
      data-async-status="error"
      className={cn(
        'flex flex-col gap-4 rounded-xl border border-destructive/30 bg-destructive/10 p-4 sm:flex-row sm:items-start sm:justify-between',
        className,
      )}
    >
      <div className="flex min-w-0 gap-3">
        <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-destructive" aria-hidden="true" />
        <div className="min-w-0">
          <p className="font-medium text-destructive">{title}</p>
          {description ? (
            <p className="mt-1 text-sm text-muted-foreground">{description}</p>
          ) : null}
          {message ? (
            <p className="mt-2 break-words text-sm text-destructive" data-testid={`${testId}-message`}>
              {message}
            </p>
          ) : null}
        </div>
      </div>
      {onRetry ? (
        <Button variant="outline" onClick={onRetry} data-testid={`${testId}-retry`}>
          <RefreshCw className="mr-2 h-4 w-4" aria-hidden="true" />
          {retryLabel}
        </Button>
      ) : null}
    </div>
  )
}
