import { beforeEach, describe, expect, it } from 'vitest'

import { clearTokens, getUserRole, getUserRoles, hasRole, setAdminToken } from '../auth'

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
