import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'

const isPortalDemoLoginEnabled = vi.fn()

vi.mock('../../config/portalDemoLogin', () => ({
  isPortalDemoLoginEnabled: () => isPortalDemoLoginEnabled(),
}))

vi.mock('../../config/apiBase', () => ({
  API_BASE_URL: 'http://localhost:8000',
}))

vi.mock('../../utils/auth', () => ({
  revokeSession: vi.fn().mockResolvedValue(undefined),
}))

import { PortalAuthProvider, usePortalAuth } from '../PortalAuthContext'

function wrapper({ children }: { children: ReactNode }) {
  return <PortalAuthProvider>{children}</PortalAuthProvider>
}

describe('PortalAuthContext demo login gate', () => {
  beforeEach(() => {
    localStorage.clear()
    sessionStorage.clear()
    isPortalDemoLoginEnabled.mockReset()
  })

  afterEach(() => {
    localStorage.clear()
    sessionStorage.clear()
  })

  it('blocks loginWithDemo when the gate is closed', async () => {
    isPortalDemoLoginEnabled.mockReturnValue(false)

    const { result } = renderHook(() => usePortalAuth(), { wrapper })

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false)
    })

    act(() => {
      result.current.loginWithDemo()
    })

    expect(result.current.isAuthenticated).toBe(false)
    expect(result.current.user).toBeNull()
    expect(result.current.error).toMatch(/disabled/i)
    expect(localStorage.getItem('portal_user')).toBeNull()
  })

  it('allows loginWithDemo when the gate is open', async () => {
    isPortalDemoLoginEnabled.mockReturnValue(true)

    const { result } = renderHook(() => usePortalAuth(), { wrapper })

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false)
    })

    act(() => {
      result.current.loginWithDemo()
    })

    expect(result.current.isDemoLoginAvailable).toBe(true)
    expect(result.current.isAuthenticated).toBe(true)
    expect(result.current.user?.isDemoUser).toBe(true)
    expect(localStorage.getItem('portal_user')).toContain('demo.employee@plantexpand.com')
  })

  it('discards a stored demo session when the gate is closed', async () => {
    isPortalDemoLoginEnabled.mockReturnValue(false)
    localStorage.setItem(
      'portal_user',
      JSON.stringify({
        id: 'demo-user-001',
        email: 'demo.employee@plantexpand.com',
        name: 'Demo Employee',
        firstName: 'Demo',
        lastName: 'Employee',
        isDemoUser: true,
      }),
    )
    localStorage.setItem('portal_session_time', Date.now().toString())

    const { result } = renderHook(() => usePortalAuth(), { wrapper })

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false)
    })

    expect(result.current.isAuthenticated).toBe(false)
    expect(result.current.user).toBeNull()
    expect(localStorage.getItem('portal_user')).toBeNull()
  })
})
