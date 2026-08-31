import { describe, expect, it, vi } from 'vitest'

const { mockHasRole, mockIsSuperuser } = vi.hoisted(() => ({
  mockHasRole: vi.fn((..._roles: string[]) => false),
  mockIsSuperuser: vi.fn(() => false),
}))

vi.mock('../../utils/auth', () => ({
  hasRole: (...roles: string[]) => mockHasRole(...roles),
  isSuperuser: () => mockIsSuperuser(),
}))

import { isPortalAuditSenior, PORTAL_AUDIT_SENIOR_ROLES } from '../portalAuditSenior'

describe('isPortalAuditSenior', () => {
  it('is false for field staff without senior roles', () => {
    mockHasRole.mockReturnValue(false)
    mockIsSuperuser.mockReturnValue(false)
    expect(isPortalAuditSenior()).toBe(false)
  })

  it('is true for supervisor and for superuser', () => {
    mockHasRole.mockImplementation((...roles: string[]) => roles.includes('supervisor'))
    mockIsSuperuser.mockReturnValue(false)
    expect(isPortalAuditSenior()).toBe(true)
    expect(PORTAL_AUDIT_SENIOR_ROLES).toContain('supervisor')
    mockHasRole.mockReturnValue(false)
    mockIsSuperuser.mockReturnValue(true)
    expect(isPortalAuditSenior()).toBe(true)
  })
})
