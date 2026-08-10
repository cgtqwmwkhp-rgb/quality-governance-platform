/**
 * Transport-timeout classification, extracted from `client.ts` so UI modules can
 * reuse it without importing the axios instance (and with it the app store,
 * toasts and env wiring). `client.ts` re-exports these for existing callers.
 */

export const WRITE_METHODS = new Set(['post', 'put', 'patch', 'delete'])

/** HTTP statuses where the *server side* reports a timeout rather than a fault. */
export const TIMEOUT_STATUS_CODES = new Set([408, 504])

/** Timeout / AbortController cancel (axios ECONNABORTED / CanceledError). */
export function isTimeoutOrAbortError(error: {
  code?: string
  message?: string
  name?: string
}): boolean {
  if (error.code === 'ECONNABORTED' || error.code === 'ERR_CANCELED') return true
  if (error.name === 'CanceledError' || error.name === 'AbortError') return true
  return typeof error.message === 'string' && error.message.toLowerCase().includes('timeout')
}

/**
 * Classify write-timeout disposition for UX. POST (and other mutations) that
 * time out are maybe-committed — reconcile/list before retrying; Idempotency-Key
 * makes a deliberate retry safe, but blind retry is discouraged.
 */
export function classifyWriteTimeoutDisposition(
  error: { code?: string; message?: string; name?: string },
  method?: string,
): 'maybe_committed' | 'safe_retry_read' | 'not_timeout' {
  if (!isTimeoutOrAbortError(error)) return 'not_timeout'
  const m = (method ?? 'get').toLowerCase()
  if (WRITE_METHODS.has(m) && m !== 'delete') {
    // DELETE is usually idempotent; POST/PUT/PATCH creates/updates may have landed.
    return 'maybe_committed'
  }
  if (m === 'delete') return 'maybe_committed'
  return 'safe_retry_read'
}

export function isMaybeCommittedTimeout(error: {
  code?: string
  message?: string
  name?: string
  config?: { method?: string }
}): boolean {
  return classifyWriteTimeoutDisposition(error, error.config?.method) === 'maybe_committed'
}
