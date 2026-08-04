/**
 * FeatureFlagProvider — asks the API which features this deployment has on.
 *
 * Why this exists
 * ---------------
 * `useFeatureFlag` resolved against `window.__FEATURE_FLAGS__`, and nothing
 * anywhere populated it. Every flagged feature was therefore invisible in every
 * environment unless somebody typed into a browser console. This provider is the
 * thing that was missing: it fetches `GET /api/v1/meta/features` and writes the
 * answer into that same object, so the documented precedence
 * (localStorage override → runtime flags → defaults) finally describes reality.
 *
 * Why the server and not a build-time bake
 * ----------------------------------------
 * The static bundle is built once and served to both staging and production, so
 * a baked value cannot differ between them. It also cannot react to the kill
 * switch: engaging that closes the API within 30 seconds, and a baked UI would
 * carry on advertising a module that now 404s.
 *
 * Subtract-only
 * -------------
 * The UI reveals a feature only on positive confirmation — from this fetch, or
 * from a cached answer a previous fetch produced. It never reveals one because
 * information is missing. That is why the visible failure mode is a nav item
 * that appears a moment late rather than one that appears and then vanishes: a
 * user can click the second kind and land on a 404.
 *
 * Context carries a version counter, not the flags themselves. The flags live on
 * `window.__FEATURE_FLAGS__` where the hook already looks, so a consumer rendered
 * outside this provider behaves exactly as it did before.
 */

import { createContext, useCallback, useEffect, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { API_BASE_URL } from '../config/apiBase'
import { getValidPlatformToken } from '../utils/auth'

const ENDPOINT = '/api/v1/meta/features'
const CACHE_KEY = 'ff_cache_v1'

/** How long a cached answer may stand in for a live one. A judgement, not a derived number. */
const CACHE_MAX_AGE_MS = 24 * 60 * 60 * 1000

/**
 * Poll interval. Not matched to the kill switch's 30s TTL on purpose: the API is
 * already closed at 30s, so UI parity buys no safety and doubles request volume.
 */
const POLL_INTERVAL_MS = 60_000

/** Every client reloads at once after a deploy; without jitter they stay in lockstep forever. */
const POLL_JITTER_MS = 10_000

const ERROR_BACKOFF_START_MS = 5_000
const ERROR_BACKOFF_MAX_MS = 60_000

const REQUEST_TIMEOUT_MS = 8_000

export interface FeatureFlagContextValue {
  /** Bumped whenever the known flag set changes, so consumers re-read. */
  version: number
  /** Force an immediate re-fetch. */
  refresh: () => void
}

export const FeatureFlagContext = createContext<FeatureFlagContextValue>({
  version: 0,
  refresh: () => {},
})

interface CachedFlags {
  flags: Record<string, boolean>
  fetchedAt: number
  scope: 'anonymous' | 'user'
}

function readCache(): CachedFlags | null {
  try {
    const raw = localStorage.getItem(CACHE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw) as Partial<CachedFlags>
    if (!parsed || typeof parsed !== 'object') return null
    if (!parsed.flags || typeof parsed.flags !== 'object') return null
    if (typeof parsed.fetchedAt !== 'number') return null
    if (Date.now() - parsed.fetchedAt > CACHE_MAX_AGE_MS) return null
    const flags: Record<string, boolean> = {}
    for (const [key, value] of Object.entries(parsed.flags)) {
      if (typeof value === 'boolean') flags[key] = value
    }
    return {
      flags,
      fetchedAt: parsed.fetchedAt,
      scope: parsed.scope === 'user' ? 'user' : 'anonymous',
    }
  } catch {
    return null
  }
}

function writeCache(entry: CachedFlags): void {
  try {
    localStorage.setItem(CACHE_KEY, JSON.stringify(entry))
  } catch {
    // Private mode or a full quota must never break rendering.
  }
}

function applyFlags(flags: Record<string, boolean>): void {
  if (typeof window === 'undefined') return
  window.__FEATURE_FLAGS__ = { ...(window.__FEATURE_FLAGS__ ?? {}), ...flags }
}

/** Seed synchronously so the very first render already has last-known-good values. */
function seedFromCache(): boolean {
  const cached = readCache()
  if (!cached) return false
  applyFlags(cached.flags)
  return true
}

export function FeatureFlagProvider({ children }: { children: ReactNode }) {
  // Runs before children render, so a returning user sees no flash.
  const [version, setVersion] = useState(() => (seedFromCache() ? 1 : 0))

  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const backoffRef = useRef(ERROR_BACKOFF_START_MS)
  /** Set when the endpoint is absent, which is a real state while the backend rolls out. */
  const unavailableRef = useRef(false)
  const tokenRef = useRef<string | null>(null)
  const mountedRef = useRef(true)

  const clearTimer = useCallback(() => {
    if (timerRef.current !== null) {
      clearTimeout(timerRef.current)
      timerRef.current = null
    }
  }, [])

  const scheduleNext = useCallback(
    (delayMs: number) => {
      clearTimer()
      if (unavailableRef.current) return
      timerRef.current = setTimeout(() => {
        void fetchFlagsRef.current?.()
      }, delayMs)
    },
    [clearTimer],
  )

  const fetchFlagsRef = useRef<(() => Promise<void>) | null>(null)

  const fetchFlags = useCallback(async () => {
    if (unavailableRef.current) return
    if (typeof document !== 'undefined' && document.visibilityState === 'hidden') {
      // A laptop with forty background tabs should not poll all night.
      scheduleNext(POLL_INTERVAL_MS)
      return
    }

    const token = getValidPlatformToken()
    tokenRef.current = token

    const controller = new AbortController()
    const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS)

    try {
      const headers: Record<string, string> = { Accept: 'application/json' }
      if (token) headers.Authorization = `Bearer ${token}`

      const response = await fetch(`${API_BASE_URL}${ENDPOINT}`, {
        method: 'GET',
        headers,
        signal: controller.signal,
      })

      if (response.status === 404) {
        // The backend predates this endpoint. Real during rollout, and permanent
        // for that session: stop asking, keep whatever we already had.
        unavailableRef.current = true
        clearTimer()
        if (import.meta.env.DEV) {
          console.info('[FeatureFlags] endpoint not deployed; using defaults for this session')
        }
        return
      }

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`)
      }

      const body = (await response.json()) as {
        flags?: Record<string, boolean>
        scope?: string
      }
      if (!body || typeof body.flags !== 'object' || body.flags === null) {
        throw new Error('malformed body')
      }

      const flags: Record<string, boolean> = {}
      for (const [key, value] of Object.entries(body.flags)) {
        if (typeof value === 'boolean') flags[key] = value
      }

      applyFlags(flags)
      writeCache({
        flags,
        fetchedAt: Date.now(),
        scope: body.scope === 'user' ? 'user' : 'anonymous',
      })
      backoffRef.current = ERROR_BACKOFF_START_MS
      if (mountedRef.current) setVersion((v) => v + 1)
      scheduleNext(POLL_INTERVAL_MS + Math.random() * POLL_JITTER_MS)
    } catch {
      // Network failure, timeout, 5xx, the service worker's synthetic offline
      // response, or a malformed body. Keep the current values and back off.
      const delay = backoffRef.current
      backoffRef.current = Math.min(backoffRef.current * 2, ERROR_BACKOFF_MAX_MS)
      scheduleNext(delay)
    } finally {
      clearTimeout(timeout)
    }
  }, [clearTimer, scheduleNext])

  fetchFlagsRef.current = fetchFlags

  const refresh = useCallback(() => {
    backoffRef.current = ERROR_BACKOFF_START_MS
    void fetchFlags()
  }, [fetchFlags])

  useEffect(() => {
    mountedRef.current = true
    void fetchFlags()

    const onVisibility = () => {
      if (document.visibilityState !== 'visible') return
      void fetchFlags()
    }

    // An anonymous answer folds in no permissions, so it must not survive sign-in.
    const onStorage = (event: StorageEvent) => {
      if (event.key === 'access_token' || event.key === 'platform_access_token') {
        void fetchFlags()
      }
    }

    document.addEventListener('visibilitychange', onVisibility)
    window.addEventListener('storage', onStorage)

    return () => {
      mountedRef.current = false
      clearTimer()
      document.removeEventListener('visibilitychange', onVisibility)
      window.removeEventListener('storage', onStorage)
    }
    // fetchFlags and clearTimer are stable useCallbacks.
  }, [fetchFlags, clearTimer])

  // A token appearing or changing within this tab produces no storage event.
  useEffect(() => {
    const interval = setInterval(() => {
      const current = getValidPlatformToken()
      if (current !== tokenRef.current) {
        tokenRef.current = current
        void fetchFlags()
      }
    }, 5_000)
    return () => clearInterval(interval)
  }, [fetchFlags])

  return (
    <FeatureFlagContext.Provider value={{ version, refresh }}>{children}</FeatureFlagContext.Provider>
  )
}

export default FeatureFlagProvider
