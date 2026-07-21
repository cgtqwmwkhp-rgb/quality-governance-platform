import { beforeEach, describe, expect, it, vi } from 'vitest'

const mockGet = vi.fn()

vi.mock('../../api/client', () => ({
  default: {
    get: (...args: unknown[]) => mockGet(...args),
  },
}))

import {
  clearPlatformReporterCache,
  resolvePlatformReporterIdentity,
} from '../platformSessionReporter'

describe('resolvePlatformReporterIdentity', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    clearPlatformReporterCache()
  })

  it('maps /auth/me profile to reporter_name and reporter_email', async () => {
    mockGet.mockResolvedValueOnce({
      data: { full_name: 'Alex Engineer', email: 'alex@example.com' },
    })

    await expect(resolvePlatformReporterIdentity()).resolves.toEqual({
      reporter_name: 'Alex Engineer',
      reporter_email: 'alex@example.com',
    })
    expect(mockGet).toHaveBeenCalledWith('/api/v1/auth/me')
  })

  it('falls back to email when full_name is absent', async () => {
    mockGet.mockResolvedValueOnce({
      data: { email: 'owner@example.com' },
    })

    await expect(resolvePlatformReporterIdentity()).resolves.toEqual({
      reporter_name: 'owner@example.com',
      reporter_email: 'owner@example.com',
    })
  })

  it('caches the resolved identity for subsequent calls', async () => {
    mockGet.mockResolvedValueOnce({
      data: { full_name: 'Cached User', email: 'cached@example.com' },
    })

    await resolvePlatformReporterIdentity()
    await resolvePlatformReporterIdentity()

    expect(mockGet).toHaveBeenCalledTimes(1)
  })

  it('returns empty identity when /auth/me fails', async () => {
    mockGet.mockRejectedValueOnce(new Error('401'))

    await expect(resolvePlatformReporterIdentity()).resolves.toEqual({})
  })
})
