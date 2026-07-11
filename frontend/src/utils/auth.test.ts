import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  clearTokens,
  getPlatformRefreshToken,
  getPlatformToken,
  hasToken,
  revokeSession,
} from './auth'

afterEach(() => {
  localStorage.clear()
  sessionStorage.clear()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('auth token helpers', () => {
  it('prefers admin localStorage token over portal session token', () => {
    sessionStorage.setItem('platform_access_token', 'portal')
    expect(getPlatformToken()).toBe('portal')
    localStorage.setItem('access_token', 'admin')
    expect(getPlatformToken()).toBe('admin')
    expect(hasToken()).toBe(true)
  })

  it('reads refresh token from admin then portal storage', () => {
    expect(getPlatformRefreshToken()).toBeNull()
    sessionStorage.setItem('platform_refresh_token', 'portal-r')
    expect(getPlatformRefreshToken()).toBe('portal-r')
    localStorage.setItem('refresh_token', 'admin-r')
    expect(getPlatformRefreshToken()).toBe('admin-r')
  })

  it('clearTokens removes admin and portal keys', () => {
    localStorage.setItem('access_token', 'a')
    localStorage.setItem('refresh_token', 'b')
    sessionStorage.setItem('platform_access_token', 'c')
    sessionStorage.setItem('platform_refresh_token', 'd')
    clearTokens()
    expect(getPlatformToken()).toBeNull()
    expect(getPlatformRefreshToken()).toBeNull()
    expect(hasToken()).toBe(false)
  })

  it('revokeSession no-ops without access token', async () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    await revokeSession()
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('revokeSession posts logout with bearer + optional refresh body', async () => {
    localStorage.setItem('access_token', 'tok')
    localStorage.setItem('refresh_token', 'ref')
    const fetchMock = vi.fn().mockResolvedValue({ ok: true })
    vi.stubGlobal('fetch', fetchMock)
    await revokeSession()
    expect(fetchMock).toHaveBeenCalled()
    const [url, init] = fetchMock.mock.calls[0]
    expect(String(url)).toContain('/api/v1/auth/logout')
    expect(init.method).toBe('POST')
    expect(init.headers.Authorization).toBe('Bearer tok')
    expect(JSON.parse(init.body)).toEqual({ refresh_token: 'ref' })
    // revokeSession is best-effort server revoke only; caller clears tokens
    expect(getPlatformToken()).toBe('tok')
  })

  it('revokeSession swallows logout fetch failures', async () => {
    localStorage.setItem('access_token', 'tok')
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('network')))
    await expect(revokeSession()).resolves.toBeUndefined()
    expect(getPlatformToken()).toBe('tok')
  })
})
