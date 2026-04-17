/**
 * useServiceWorkerAuthBridge
 *
 * Listens for `AUTH_REQUIRED` messages posted by the service worker (sw.js)
 * when an API fetch it intercepts comes back 401/403, and triggers a silent
 * token refresh via the same single-flight refresh used by the axios
 * interceptor.
 *
 * Why this matters:
 *   - The SW intercepts navigation/API GETs (see networkFirstApi /
 *     networkFirstApiWithCache) and posts `{ type: 'AUTH_REQUIRED' }` to
 *     every controlled client when an auth failure happens at that layer.
 *   - Without a listener, that message is a no-op: the user keeps seeing
 *     the cached/empty state and the next axios call is the first thing
 *     that notices their session needs refreshing.
 *   - With this bridge, we attempt a refresh as soon as the SW reports the
 *     problem. If it succeeds, subsequent requests just work. If it fails,
 *     the next axios 401 will fall through to clearAndRedirectToLogin.
 *
 * The hook is intentionally tiny: it does NOT itself decide to log the user
 * out — that decision stays with the axios response interceptor, which has
 * the full error context.
 */
import { useEffect } from 'react'
import { refreshSession } from '../api/client'
import { getPlatformRefreshToken, shouldRefreshToken, getPlatformToken } from '../utils/auth'

interface UseServiceWorkerAuthBridgeOptions {
  enabled?: boolean
}

interface ServiceWorkerAuthMessage {
  type: 'AUTH_REQUIRED'
  status?: number
}

function isAuthRequiredMessage(data: unknown): data is ServiceWorkerAuthMessage {
  return (
    typeof data === 'object' &&
    data !== null &&
    (data as { type?: unknown }).type === 'AUTH_REQUIRED'
  )
}

export function useServiceWorkerAuthBridge(
  options: UseServiceWorkerAuthBridgeOptions = {},
): void {
  const { enabled = true } = options

  useEffect(() => {
    if (!enabled) return
    if (typeof navigator === 'undefined' || !('serviceWorker' in navigator)) return

    let inFlight = false

    const handleMessage = (event: MessageEvent) => {
      if (!isAuthRequiredMessage(event.data)) return

      // No refresh token? Nothing we can do — let the next axios call surface
      // the 401 and route through the interceptor's clear-and-redirect path.
      const refreshToken = getPlatformRefreshToken()
      if (!refreshToken) return

      // If the access token still looks fresh, the 401 was probably a stale
      // cache from before refresh — re-issuing API calls will work without
      // hitting the refresh endpoint again.
      const accessToken = getPlatformToken()
      if (accessToken && !shouldRefreshToken(accessToken)) return

      if (inFlight) return
      inFlight = true

      if (import.meta.env.DEV) {
        console.info('[SW Auth Bridge] AUTH_REQUIRED received - attempting silent refresh')
      }

      refreshSession()
        .then((token) => {
          if (import.meta.env.DEV) {
            console.info(
              `[SW Auth Bridge] silent refresh ${token ? 'succeeded' : 'failed (will fall through to axios on next 401)'}`,
            )
          }
        })
        .catch(() => {
          /* swallow — axios will clear+redirect on the next real 401 */
        })
        .finally(() => {
          inFlight = false
        })
    }

    navigator.serviceWorker.addEventListener('message', handleMessage)
    return () => {
      navigator.serviceWorker.removeEventListener('message', handleMessage)
    }
  }, [enabled])
}
