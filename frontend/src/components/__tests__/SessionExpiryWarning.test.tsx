import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, render, renderHook, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

const refreshSession = vi.fn()

vi.mock('../../api/client', () => ({
  refreshSession: () => refreshSession(),
}))

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, fallback?: string) => fallback ?? key,
    i18n: { language: 'en' },
  }),
  initReactI18next: { type: '3rdParty', init: () => {} },
}))

/** Minimal unsigned JWT — only the `exp` claim is ever read client-side. */
function tokenExpiringIn(seconds: number): string {
  const payload = btoa(JSON.stringify({ exp: Math.floor(Date.now() / 1000) + seconds }))
  return `header.${payload}.signature`
}

describe('PX-179 session expiry warning', () => {
  beforeEach(() => {
    localStorage.clear()
    sessionStorage.clear()
    refreshSession.mockReset()
    refreshSession.mockResolvedValue('new-token')
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  describe('useSessionKeepalive warning state', () => {
    it('stays quiet while the session has plenty of time left', async () => {
      localStorage.setItem('access_token', tokenExpiringIn(3600))
      const { useSessionKeepalive } = await import('../../hooks/useSessionKeepalive')

      const { result } = renderHook(() => useSessionKeepalive({ enabled: true }))

      expect(result.current.expiryImminent).toBe(false)
    })

    it('warns once inside the window, which only happens after silent refresh has failed', async () => {
      // 60s left: the keepalive schedules its silent refresh at 300s out, so
      // reaching this point at all means that refresh did not succeed.
      localStorage.setItem('access_token', tokenExpiringIn(60))
      const { useSessionKeepalive } = await import('../../hooks/useSessionKeepalive')

      const { result } = renderHook(() => useSessionKeepalive({ enabled: true }))

      await waitFor(() => expect(result.current.expiryImminent).toBe(true))
    })

    it('does not warn when logged out', async () => {
      localStorage.setItem('access_token', tokenExpiringIn(30))
      const { useSessionKeepalive } = await import('../../hooks/useSessionKeepalive')

      const { result } = renderHook(() => useSessionKeepalive({ enabled: false }))

      expect(result.current.expiryImminent).toBe(false)
    })

    it('clears the warning when the user extends the session', async () => {
      localStorage.setItem('access_token', tokenExpiringIn(60))
      const { useSessionKeepalive } = await import('../../hooks/useSessionKeepalive')

      const { result } = renderHook(() => useSessionKeepalive({ enabled: true }))
      await waitFor(() => expect(result.current.expiryImminent).toBe(true))

      await act(async () => {
        await result.current.extendSession()
      })

      expect(refreshSession).toHaveBeenCalled()
      expect(result.current.expiryImminent).toBe(false)
      expect(result.current.extendFailed).toBe(false)
    })

    it('keeps the warning up and records the failure when refresh is refused', async () => {
      localStorage.setItem('access_token', tokenExpiringIn(60))
      refreshSession.mockResolvedValue(null)
      const { useSessionKeepalive } = await import('../../hooks/useSessionKeepalive')

      const { result } = renderHook(() => useSessionKeepalive({ enabled: true }))
      await waitFor(() => expect(result.current.expiryImminent).toBe(true))

      await act(async () => {
        await result.current.extendSession()
      })

      expect(result.current.expiryImminent).toBe(true)
      expect(result.current.extendFailed).toBe(true)
    })

    it('survives a rejected refresh instead of leaving the shell stuck extending', async () => {
      localStorage.setItem('access_token', tokenExpiringIn(60))
      refreshSession.mockRejectedValue(new Error('offline'))
      const { useSessionKeepalive } = await import('../../hooks/useSessionKeepalive')

      const { result } = renderHook(() => useSessionKeepalive({ enabled: true }))

      await act(async () => {
        await expect(result.current.extendSession()).resolves.toBe(false)
      })

      expect(result.current.extending).toBe(false)
      expect(result.current.extendFailed).toBe(true)
    })
  })

  // Rendering is gated by Layout (see Layout.a11y), which also lazy-loads this
  // component — so the banner itself has no `open` prop to test.
  describe('SessionExpiryWarning banner', () => {
    it('announces the warning and offers a way to stay signed in', async () => {
      const user = userEvent.setup()
      const onExtend = vi.fn()
      const SessionExpiryWarning = (await import('../SessionExpiryWarning')).default

      render(<SessionExpiryWarning onExtend={onExtend} />)

      const alert = screen.getByRole('alert')
      expect(alert).toHaveTextContent('Your session expires soon.')
      // Assertive: two minutes is not long enough to wait for a polite queue.
      expect(alert).toHaveAttribute('aria-live', 'assertive')

      await user.click(screen.getByRole('button', { name: 'Stay signed in' }))
      expect(onExtend).toHaveBeenCalledTimes(1)
    })

    it('disables the action while the extend request is in flight', async () => {
      const SessionExpiryWarning = (await import('../SessionExpiryWarning')).default

      render(<SessionExpiryWarning extending onExtend={() => {}} />)

      expect(screen.getByRole('button', { name: 'Stay signed in' })).toBeDisabled()
    })
  })
})
