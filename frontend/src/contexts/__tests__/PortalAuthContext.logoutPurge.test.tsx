/**
 * AUD-F6 — signing out clears the audit device ledger, and does it in time.
 *
 * The ledger is namespaced by the access token's `sub`, so the purge has to
 * happen while the token is still readable. Once `clearAuthState()` has run there
 * is no way to work out which rows belonged to the auditor who just left, and a
 * shared tablet would keep their answers and unsynced photos for whoever picks it
 * up next.
 *
 * The order is therefore the assertion, not just the call.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'

const calls: string[] = []

vi.mock('../../config/portalDemoLogin', () => ({
  isPortalDemoLoginEnabled: () => true,
}))

vi.mock('../../config/apiBase', () => ({
  API_BASE_URL: 'http://localhost:8000',
}))

vi.mock('../../utils/auth', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../utils/auth')>()
  return {
    ...actual,
    revokeSession: vi.fn(async () => {
      calls.push('revokeSession')
    }),
    getValidPlatformToken: vi.fn().mockReturnValue(null),
    establishPlatformSession: vi.fn(),
    clearAuthState: vi.fn(() => {
      calls.push('clearAuthState')
    }),
  }
})

vi.mock('../../services/auditDraftStore', () => ({
  purgeDeviceLedgerForCurrentSession: vi.fn(async () => {
    calls.push('purgeDeviceLedger')
  }),
}))

import { PortalAuthProvider, usePortalAuth } from '../PortalAuthContext'
import { purgeDeviceLedgerForCurrentSession } from '../../services/auditDraftStore'

function wrapper({ children }: { children: ReactNode }) {
  return <PortalAuthProvider>{children}</PortalAuthProvider>
}

describe('portal sign-out purges the audit device ledger', () => {
  beforeEach(() => {
    calls.length = 0
    localStorage.clear()
    sessionStorage.clear()
  })

  afterEach(() => {
    localStorage.clear()
    sessionStorage.clear()
  })

  it('purges before the token is cleared', async () => {
    const { result } = renderHook(() => usePortalAuth(), { wrapper })
    await waitFor(() => {
      expect(result.current.isLoading).toBe(false)
    })

    await act(async () => {
      await result.current.logout()
    })

    expect(purgeDeviceLedgerForCurrentSession).toHaveBeenCalledOnce()
    expect(calls).toEqual(['revokeSession', 'purgeDeviceLedger', 'clearAuthState'])
  })
})
