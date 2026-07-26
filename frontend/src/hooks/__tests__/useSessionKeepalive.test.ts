import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const refreshSession = vi.fn(async () => 'new-token')
const getPlatformToken = vi.fn<() => string | null>()
const getPlatformRefreshToken = vi.fn<() => string | null>()
const getTokenExpirySeconds = vi.fn<(token: string) => number | null>()
const shouldRefreshToken = vi.fn<(token: string) => boolean>()

vi.mock('../../api/client', () => ({
  refreshSession: (...args: unknown[]) => refreshSession(...args),
}))

vi.mock('../../utils/auth', () => ({
  TOKEN_REFRESH_LEAD_SECONDS: 300,
  SESSION_WARNING_LEAD_SECONDS: 120,
  getPlatformToken: (...args: unknown[]) => getPlatformToken(...args),
  getPlatformRefreshToken: (...args: unknown[]) => getPlatformRefreshToken(...args),
  getTokenExpirySeconds: (...args: unknown[]) => getTokenExpirySeconds(...(args as [string])),
  shouldRefreshToken: (...args: unknown[]) => shouldRefreshToken(...(args as [string])),
  // Mirrors the real helper so the expiry-warning poll sees the same clock as
  // the refresh scheduler these tests already drive via getTokenExpirySeconds.
  getSecondsUntilExpiry: (token: string) => {
    const exp = getTokenExpirySeconds(token)
    return exp === null ? null : exp - Math.floor(Date.now() / 1000)
  },
}))

import { useSessionKeepalive } from '../useSessionKeepalive'

describe('useSessionKeepalive', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    refreshSession.mockReset().mockResolvedValue('new-token')
    getPlatformToken.mockReset()
    getPlatformRefreshToken.mockReset()
    getTokenExpirySeconds.mockReset()
    shouldRefreshToken.mockReset()
  })

  afterEach(() => {
    vi.clearAllTimers()
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  it('is a no-op when disabled', () => {
    getPlatformToken.mockReturnValue('access')
    getPlatformRefreshToken.mockReturnValue('refresh')
    getTokenExpirySeconds.mockReturnValue(Math.floor(Date.now() / 1000) + 3600)

    const { unmount } = renderHook(() => useSessionKeepalive({ enabled: false }))
    expect(refreshSession).not.toHaveBeenCalled()
    unmount()
  })

  it('does not schedule refresh when access or refresh token is missing', () => {
    getPlatformToken.mockReturnValue(null)
    getPlatformRefreshToken.mockReturnValue(null)

    const { unmount } = renderHook(() => useSessionKeepalive())
    expect(refreshSession).not.toHaveBeenCalled()
    unmount()
  })

  it('schedules proactive refresh and invokes refreshSession when the timer fires', async () => {
    const nowSec = 1_700_000_000
    vi.setSystemTime(nowSec * 1000)
    getPlatformToken.mockReturnValue('access')
    getPlatformRefreshToken.mockReturnValue('refresh')
    // 301s to expiry → secondsUntilRefresh = 1 → clamped to MIN_TIMER_MS (15s)
    getTokenExpirySeconds.mockReturnValue(nowSec + 301)

    const { unmount } = renderHook(() => useSessionKeepalive())

    await act(async () => {
      await vi.advanceTimersByTimeAsync(15_000)
    })

    expect(refreshSession).toHaveBeenCalledTimes(1)
    unmount()
  })

  it('refreshes on visibilitychange when the token is inside the refresh window', async () => {
    getPlatformToken.mockReturnValue('access')
    getPlatformRefreshToken.mockReturnValue('refresh')
    getTokenExpirySeconds.mockReturnValue(Math.floor(Date.now() / 1000) + 3600)
    shouldRefreshToken.mockReturnValue(true)

    const { unmount } = renderHook(() => useSessionKeepalive())

    await act(async () => {
      Object.defineProperty(document, 'visibilityState', {
        configurable: true,
        get: () => 'visible',
      })
      document.dispatchEvent(new Event('visibilitychange'))
    })

    expect(shouldRefreshToken).toHaveBeenCalled()
    expect(refreshSession).toHaveBeenCalled()
    unmount()
  })

  it('refreshes on online reconnect when shouldRefreshToken is true', async () => {
    getPlatformToken.mockReturnValue('access')
    getPlatformRefreshToken.mockReturnValue('refresh')
    getTokenExpirySeconds.mockReturnValue(Math.floor(Date.now() / 1000) + 3600)
    shouldRefreshToken.mockReturnValue(true)

    const { unmount } = renderHook(() => useSessionKeepalive())

    await act(async () => {
      window.dispatchEvent(new Event('online'))
    })

    expect(refreshSession).toHaveBeenCalled()
    unmount()
  })

  it('skips resume refresh when shouldRefreshToken is false', async () => {
    getPlatformToken.mockReturnValue('access')
    getPlatformRefreshToken.mockReturnValue('refresh')
    getTokenExpirySeconds.mockReturnValue(Math.floor(Date.now() / 1000) + 3600)
    shouldRefreshToken.mockReturnValue(false)

    const { unmount } = renderHook(() => useSessionKeepalive())
    refreshSession.mockClear()

    await act(async () => {
      window.dispatchEvent(new Event('focus'))
    })

    expect(shouldRefreshToken).toHaveBeenCalled()
    expect(refreshSession).not.toHaveBeenCalled()
    unmount()
  })

  // PX-179: the shell needs to know the session is ending so it can say so.
  it('does not flag expiry while the token is outside the warning window', () => {
    getPlatformToken.mockReturnValue('access')
    getPlatformRefreshToken.mockReturnValue('refresh')
    getTokenExpirySeconds.mockReturnValue(Math.floor(Date.now() / 1000) + 3600)

    const { result, unmount } = renderHook(() => useSessionKeepalive())

    expect(result.current.expiryImminent).toBe(false)
    unmount()
  })

  it('flags expiry once inside the warning window', () => {
    getPlatformToken.mockReturnValue('access')
    getPlatformRefreshToken.mockReturnValue('refresh')
    getTokenExpirySeconds.mockReturnValue(Math.floor(Date.now() / 1000) + 60)

    const { result, unmount } = renderHook(() => useSessionKeepalive())

    expect(result.current.expiryImminent).toBe(true)
    unmount()
  })

  it('does not flag expiry once signed out', () => {
    getPlatformToken.mockReturnValue(null)
    getPlatformRefreshToken.mockReturnValue(null)

    const { result, unmount } = renderHook(() => useSessionKeepalive())

    expect(result.current.expiryImminent).toBe(false)
    unmount()
  })
})
