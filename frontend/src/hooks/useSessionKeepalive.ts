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
import { useCallback, useEffect, useRef, useState } from 'react'
import { refreshSession } from '../api/client'
import {
  getPlatformRefreshToken,
  getPlatformToken,
  getSecondsUntilExpiry,
  getTokenExpirySeconds,
  SESSION_WARNING_LEAD_SECONDS,
  shouldRefreshToken,
  TOKEN_REFRESH_LEAD_SECONDS,
} from '../utils/auth'

const MIN_TIMER_MS = 15_000 // never schedule sooner than 15s
const MAX_TIMER_MS = 25 * 60 * 1000 // never schedule later than 25min
const WARNING_POLL_MS = 10_000

interface UseSessionKeepaliveOptions {
  enabled?: boolean
}

export interface SessionKeepaliveState {
  /**
   * True once the session is inside the warning window with no successful
   * silent refresh — i.e. the user is genuinely about to be signed out.
   */
  expiryImminent: boolean
  /** True while a user-initiated "stay signed in" refresh is in flight. */
  extending: boolean
  /** True when the most recent extend attempt failed; the session will end. */
  extendFailed: boolean
  /** Attempt an immediate refresh. Resolves true when the session was extended. */
  extendSession: () => Promise<boolean>
}

export function useSessionKeepalive(
  options: UseSessionKeepaliveOptions = {},
): SessionKeepaliveState {
  const { enabled = true } = options
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const enabledRef = useRef(enabled)
  enabledRef.current = enabled

  const [expiryImminent, setExpiryImminent] = useState(false)
  const [extending, setExtending] = useState(false)
  const [extendFailed, setExtendFailed] = useState(false)

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

  // Watch the countdown so the shell can warn before the session actually
  // ends. Read-only: this poll never refreshes, so it cannot race the
  // scheduler above (PX-179).
  useEffect(() => {
    if (!enabled) {
      setExpiryImminent(false)
      setExtendFailed(false)
      return
    }

    const evaluate = () => {
      const token = getPlatformToken()
      if (!token) {
        setExpiryImminent(false)
        return
      }
      const remaining = getSecondsUntilExpiry(token)
      // An unreadable `exp` gives us nothing honest to warn about; the 401
      // interceptor remains the backstop.
      if (remaining === null) {
        setExpiryImminent(false)
        return
      }
      const imminent = remaining <= SESSION_WARNING_LEAD_SECONDS
      setExpiryImminent(imminent)
      if (!imminent) setExtendFailed(false)
    }

    evaluate()
    const handle = setInterval(evaluate, WARNING_POLL_MS)
    const onVisible = () => {
      if (document.visibilityState === 'visible') evaluate()
    }
    document.addEventListener('visibilitychange', onVisible)

    return () => {
      clearInterval(handle)
      document.removeEventListener('visibilitychange', onVisible)
    }
  }, [enabled])

  const extendSession = useCallback(async () => {
    setExtending(true)
    try {
      const token = await refreshSession()
      if (token) {
        setExpiryImminent(false)
        setExtendFailed(false)
        return true
      }
      setExtendFailed(true)
      return false
    } catch {
      setExtendFailed(true)
      return false
    } finally {
      setExtending(false)
    }
  }, [])

  return { expiryImminent, extending, extendFailed, extendSession }
}

export default useSessionKeepalive
