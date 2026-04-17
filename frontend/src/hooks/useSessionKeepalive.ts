/**
 * useSessionKeepalive
 *
 * Keeps the access JWT warm for long sessions (e.g. an auditor working
 * through a tablet questionnaire for >30 minutes between API calls).
 *
 * Strategy:
 *   1. Schedule a proactive refresh ~5 minutes before the access token's
 *      `exp` claim. After each refresh we re-schedule.
 *   2. On `visibilitychange` (tab becomes visible) and `pageshow` (BFCache
 *      restore on iOS Safari), if the token is expired or within the
 *      refresh window, refresh immediately so the user's first API call
 *      after resuming carries a valid bearer.
 *   3. On `online` (Wi-Fi/cellular reconnect), do the same.
 *
 * The hook is a no-op when there is no token (logged out) or no refresh
 * token. All refreshes go through the single-flight `refreshSession()`
 * helper so concurrent callers share one in-flight request.
 */
import { useEffect, useRef } from 'react'
import { refreshSession } from '../api/client'
import {
  getPlatformRefreshToken,
  getPlatformToken,
  getTokenExpirySeconds,
  shouldRefreshToken,
  TOKEN_REFRESH_LEAD_SECONDS,
} from '../utils/auth'

const MIN_TIMER_MS = 15_000 // never schedule sooner than 15s
const MAX_TIMER_MS = 25 * 60 * 1000 // never schedule later than 25min

interface UseSessionKeepaliveOptions {
  enabled?: boolean
}

export function useSessionKeepalive(options: UseSessionKeepaliveOptions = {}): void {
  const { enabled = true } = options
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const enabledRef = useRef(enabled)
  enabledRef.current = enabled

  useEffect(() => {
    if (!enabled) return

    let cancelled = false

    const clearTimer = () => {
      if (timerRef.current !== null) {
        clearTimeout(timerRef.current)
        timerRef.current = null
      }
    }

    const scheduleNext = () => {
      clearTimer()
      const token = getPlatformToken()
      if (!token) return
      const refreshToken = getPlatformRefreshToken()
      if (!refreshToken) return

      const exp = getTokenExpirySeconds(token)
      if (exp === null) return

      const nowSec = Math.floor(Date.now() / 1000)
      const secondsUntilRefresh = exp - nowSec - TOKEN_REFRESH_LEAD_SECONDS
      const ms = Math.min(
        MAX_TIMER_MS,
        Math.max(MIN_TIMER_MS, Math.floor(secondsUntilRefresh * 1000)),
      )

      timerRef.current = setTimeout(() => {
        timerRef.current = null
        if (cancelled || !enabledRef.current) return
        // Fire and forget; refreshSession is single-flight and never throws.
        void refreshSession().finally(() => {
          if (!cancelled && enabledRef.current) scheduleNext()
        })
      }, ms)
    }

    const refreshIfNeeded = async (reason: string) => {
      if (!enabledRef.current) return
      const token = getPlatformToken()
      if (!token) return
      const refreshToken = getPlatformRefreshToken()
      if (!refreshToken) return
      if (!shouldRefreshToken(token)) return
      if (import.meta.env.DEV) {
        console.log(`[SessionKeepalive] Refreshing on ${reason}`)
      }
      await refreshSession()
      if (!cancelled) scheduleNext()
    }

    const onVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        void refreshIfNeeded('visibilitychange')
      }
    }
    const onPageShow = (event: PageTransitionEvent) => {
      if (event.persisted) {
        void refreshIfNeeded('pageshow:bfcache')
      } else {
        void refreshIfNeeded('pageshow')
      }
    }
    const onOnline = () => {
      void refreshIfNeeded('online')
    }
    const onFocus = () => {
      void refreshIfNeeded('focus')
    }

    document.addEventListener('visibilitychange', onVisibilityChange)
    window.addEventListener('pageshow', onPageShow)
    window.addEventListener('online', onOnline)
    window.addEventListener('focus', onFocus)
    scheduleNext()

    return () => {
      cancelled = true
      clearTimer()
      document.removeEventListener('visibilitychange', onVisibilityChange)
      window.removeEventListener('pageshow', onPageShow)
      window.removeEventListener('online', onOnline)
      window.removeEventListener('focus', onFocus)
    }
  }, [enabled])
}

export default useSessionKeepalive
