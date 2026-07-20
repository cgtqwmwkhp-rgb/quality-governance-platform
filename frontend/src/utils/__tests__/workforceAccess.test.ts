import { describe, expect, it, vi, beforeEach } from 'vitest'
import { hasRole, isSuperuser } from '../auth'
import { isWorkforceManager } from '../workforceAccess'

vi.mock('../auth', () => ({
  hasRole: vi.fn(),
  isSuperuser: vi.fn(),
}))

describe('isWorkforceManager', () => {
  beforeEach(() => {
    vi.mocked(hasRole).mockReturnValue(false)
    vi.mocked(isSuperuser).mockReturnValue(false)
  })

  it('returns true for superuser', () => {
    vi.mocked(isSuperuser).mockReturnValue(true)
    expect(isWorkforceManager()).toBe(true)
  })

  it('returns true for admin or supervisor roles', () => {
    vi.mocked(hasRole).mockImplementation((...roles: string[]) =>
      roles.some((r) => r === 'admin' || r === 'supervisor'),
    )
    expect(isWorkforceManager()).toBe(true)
  })

  it('returns false for staff without manager facet', () => {
    expect(isWorkforceManager()).toBe(false)
  })
})
