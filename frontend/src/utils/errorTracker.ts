/**
 * Centralized error tracking utility.
 *
 * Wraps console.error with structured context so a future integration
 * (Sentry, Application Insights, etc.) can be dropped in without
 * changing call sites.
 */

interface ErrorContext {
  component?: string
  action?: string
  userId?: number
  extra?: Record<string, unknown>
}

export function trackError(error: unknown, context?: ErrorContext): void {
  const msg = error instanceof Error ? error.message : String(error)

  // Structured log for observability pipelines
  console.error(
    `[QGP Error] ${context?.component ?? 'unknown'}/${context?.action ?? 'unknown'}: ${msg}`,
    { error, ...context },
  )

  // Future: send to Sentry / App Insights
  // Sentry.captureException(error, { extra: context })
}

export default trackError
