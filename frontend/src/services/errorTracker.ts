interface ErrorEvent {
  message: string
  stack?: string
  componentStack?: string
  url: string
  timestamp: string
  userAgent: string
  extra?: Record<string, unknown>
}

const ERROR_ENDPOINT = import.meta.env.VITE_ERROR_ENDPOINT
const MAX_ERRORS_PER_SESSION = 50
let errorCount = 0

function sendError(event: ErrorEvent): void {
  if (errorCount >= MAX_ERRORS_PER_SESSION) return
  errorCount++

  if (ERROR_ENDPOINT) {
    try {
      navigator.sendBeacon(ERROR_ENDPOINT, JSON.stringify(event))
    } catch {
      // Silently fail - error tracking should never break the app
    }
  }

  if (import.meta.env.DEV) {
    console.error('[ErrorTracker]', event.message, event)
  }
}

export function trackError(error: unknown, extra?: Record<string, unknown>): void {
  const err = error instanceof Error ? error : new Error(String(error))
  sendError({
    message: err.message,
    stack: err.stack,
    url: window.location.href,
    timestamp: new Date().toISOString(),
    userAgent: navigator.userAgent,
    extra,
  })
}

export function trackComponentError(error: Error, componentStack: string | null | undefined): void {
  sendError({
    message: error.message,
    stack: error.stack,
    componentStack: componentStack ?? undefined,
    url: window.location.href,
    timestamp: new Date().toISOString(),
    userAgent: navigator.userAgent,
  })
}

export function initErrorTracking(): void {
  window.addEventListener('error', (event) => {
    trackError(event.error ?? event.message, {
      filename: event.filename,
      lineno: event.lineno,
      colno: event.colno,
    })
  })

  window.addEventListener('unhandledrejection', (event) => {
    trackError(event.reason ?? 'Unhandled Promise rejection', {
      type: 'unhandledrejection',
    })
  })
}
