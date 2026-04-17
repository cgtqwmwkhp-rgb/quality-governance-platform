import { beforeEach, describe, expect, it } from 'vitest'

import {
  clearTokens,
  getTokenExpirySeconds,
  getUserRole,
  getUserRoles,
  hasRole,
  isTokenExpired,
  setAdminToken,
  shouldRefreshToken,
  TOKEN_REFRESH_LEAD_SECONDS,
  TOKEN_SKEW_SECONDS,
} from '../auth'

function createToken(payload: Record<string, unknown>): string {
  const encoded = btoa(JSON.stringify(payload))
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=+$/g, '')
  return `header.${encoded}.signature`
}

describe('auth role utilities', () => {
  beforeEach(() => {
    clearTokens()
  })

  it('supports roles arrays from JWT claims', () => {
    setAdminToken(createToken({ roles: ['admin', 'supervisor'] }))

    expect(getUserRoles()).toEqual(['admin', 'supervisor'])
    expect(getUserRole()).toBe('admin')
    expect(hasRole('supervisor')).toBe(true)
    expect(hasRole('viewer')).toBe(false)
  })

  it('supports comma-separated role strings', () => {
    setAdminToken(createToken({ roles: 'admin, supervisor' }))

    expect(getUserRoles()).toEqual(['admin', 'supervisor'])
    expect(hasRole('admin')).toBe(true)
    expect(hasRole('supervisor')).toBe(true)
  })
})

describe('auth token expiry helpers', () => {
  beforeEach(() => {
    clearTokens()
  })

  it('extracts the JWT exp claim', () => {
    const future = Math.floor(Date.now() / 1000) + 600
    const token = createToken({ exp: future })
    expect(getTokenExpirySeconds(token)).toBe(future)
  })

  it('returns null when exp is missing or invalid', () => {
    expect(getTokenExpirySeconds(createToken({}))).toBeNull()
    expect(getTokenExpirySeconds('not-a-jwt')).toBeNull()
  })

  it('treats a token still inside the skew buffer as not expired', () => {
    // exp is 60s in the past — still within the 120s skew buffer
    const exp = Math.floor(Date.now() / 1000) - 60
    expect(isTokenExpired(createToken({ exp }))).toBe(false)
  })

  it('treats a token past exp + skew buffer as expired', () => {
    const exp = Math.floor(Date.now() / 1000) - (TOKEN_SKEW_SECONDS + 5)
    expect(isTokenExpired(createToken({ exp }))).toBe(true)
  })

  it('treats a token expiring inside the proactive refresh window as needing refresh', () => {
    // exp is well within the lead window
    const exp = Math.floor(Date.now() / 1000) + Math.floor(TOKEN_REFRESH_LEAD_SECONDS / 2)
    expect(shouldRefreshToken(createToken({ exp }))).toBe(true)
  })

  it('treats a token comfortably ahead of the refresh window as not needing refresh', () => {
    const exp = Math.floor(Date.now() / 1000) + TOKEN_REFRESH_LEAD_SECONDS + 600
    expect(shouldRefreshToken(createToken({ exp }))).toBe(false)
  })

  it('treats a malformed token as needing refresh', () => {
    expect(shouldRefreshToken('not-a-jwt')).toBe(true)
  })
})
