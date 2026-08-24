import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  clearAuthState,
  clearReturnPath,
  clearTokens,
  consumeReturnPath,
  establishPlatformSession,
  getPlatformRefreshToken,
  getPlatformToken,
  hasToken,
  isSafeReturnPath,
  peekReturnPath,
  revokeSession,
  stashReturnPath,
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

  it('establishPlatformSession mirrors JWT into admin and portal stores', () => {
    establishPlatformSession('shared-access', 'shared-refresh')
    expect(localStorage.getItem('access_token')).toBe('shared-access')
    expect(localStorage.getItem('refresh_token')).toBe('shared-refresh')
    expect(sessionStorage.getItem('platform_access_token')).toBe('shared-access')
    expect(sessionStorage.getItem('platform_refresh_token')).toBe('shared-refresh')
    expect(getPlatformToken()).toBe('shared-access')
    expect(getPlatformRefreshToken()).toBe('shared-refresh')
  })

  it('clearAuthState wipes tokens plus portal profile/oauth scratch', () => {
    establishPlatformSession('tok', 'ref')
    localStorage.setItem('portal_user', '{"email":"a@b.c"}')
    localStorage.setItem('portal_session_time', '1')
    sessionStorage.setItem('oauth_state', 'x')
    sessionStorage.setItem('portal_oauth_nonce', 'y')
    clearAuthState()
    expect(getPlatformToken()).toBeNull()
    expect(localStorage.getItem('portal_user')).toBeNull()
    expect(localStorage.getItem('portal_session_time')).toBeNull()
    expect(sessionStorage.getItem('oauth_state')).toBeNull()
    expect(sessionStorage.getItem('portal_oauth_nonce')).toBeNull()
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

// PX-179: an expired session used to dump the user on /login with no way back
// to what they were doing.
describe('session return path', () => {
  it('round-trips an app-relative path, including its query string', () => {
    stashReturnPath('/audits/42/execute?tab=questions')
    expect(peekReturnPath()).toBe('/audits/42/execute?tab=questions')
    expect(consumeReturnPath()).toBe('/audits/42/execute?tab=questions')
  })

  it('consumes once, so a re-render cannot replay a stale destination', () => {
    stashReturnPath('/risk-register')
    expect(consumeReturnPath()).toBe('/risk-register')
    expect(consumeReturnPath()).toBeNull()
  })

  it('refuses destinations that would leave the origin', () => {
    // Protocol-relative and absolute URLs are the classic open-redirect
    // payloads: //evil.example resolves to https://evil.example.
    for (const hostile of [
      '//evil.example/phish',
      '/\\evil.example',
      'https://evil.example',
      'javascript:alert(1)',
      'dashboard',
    ]) {
      expect(isSafeReturnPath(hostile)).toBe(false)
      stashReturnPath(hostile)
      expect(peekReturnPath()).toBeNull()
    }
  })

  it('refuses login surfaces, which would bounce the user in a loop', () => {
    for (const loop of ['/login', '/portal/login', '/reset-password?token=x']) {
      expect(isSafeReturnPath(loop)).toBe(false)
      stashReturnPath(loop)
      expect(peekReturnPath()).toBeNull()
    }
  })

  it('clearAuthState records where the session was lost', () => {
    window.history.pushState({}, '', '/audits/7/execute?q=1')
    establishPlatformSession('tok', 'ref')

    clearAuthState()

    expect(getPlatformToken()).toBeNull()
    expect(peekReturnPath()).toBe('/audits/7/execute?q=1')
  })

  it('does not record a return path when the session is lost on the login page', () => {
    window.history.pushState({}, '', '/login')
    establishPlatformSession('tok', 'ref')

    clearAuthState()

    expect(peekReturnPath()).toBeNull()
  })

  it('clearReturnPath drops the stash for a deliberate sign-out', () => {
    stashReturnPath('/dashboard')
    clearReturnPath()
    expect(peekReturnPath()).toBeNull()
  })
})
