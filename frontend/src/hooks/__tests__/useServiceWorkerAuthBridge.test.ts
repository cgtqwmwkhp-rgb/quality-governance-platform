import { describe, it, expect, beforeEach, vi } from 'vitest'
import { renderHook } from '@testing-library/react'

const refreshSession = vi.fn()
const getPlatformRefreshToken = vi.fn()
const shouldRefreshToken = vi.fn()
const getPlatformToken = vi.fn()

vi.mock('../../api/client', () => ({
  refreshSession: (...args: unknown[]) => refreshSession(...args),
}))

vi.mock('../../utils/auth', () => ({
  getPlatformRefreshToken: (...args: unknown[]) => getPlatformRefreshToken(...args),
  shouldRefreshToken: (...args: unknown[]) => shouldRefreshToken(...args),
  getPlatformToken: (...args: unknown[]) => getPlatformToken(...args),
}))

import { useServiceWorkerAuthBridge } from '../useServiceWorkerAuthBridge'

// Capture the listener registered by the hook so we can synthesise messages.
let messageListener: ((event: MessageEvent) => void) | null = null

function installServiceWorkerShim() {
  Object.defineProperty(navigator, 'serviceWorker', {
    configurable: true,
    value: {
      addEventListener: vi.fn((type: string, fn: (event: MessageEvent) => void) => {
        if (type === 'message') messageListener = fn
      }),
      removeEventListener: vi.fn((type: string, fn: (event: MessageEvent) => void) => {
        if (type === 'message' && messageListener === fn) messageListener = null
      }),
    },
  })
}

function fireSwMessage(data: unknown) {
  if (!messageListener) throw new Error('no listener registered')
  messageListener(new MessageEvent('message', { data }))
}

describe('useServiceWorkerAuthBridge', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    messageListener = null
    // Reinstall a fresh shim each test. We do NOT delete it in afterEach
    // because React's effect cleanup (which calls removeEventListener) runs
    // *after* afterEach in some scheduling paths and would otherwise crash
    // on an undefined navigator.serviceWorker.
    installServiceWorkerShim()
  })

  it('triggers refreshSession when AUTH_REQUIRED arrives and the access token needs refresh', async () => {
    getPlatformRefreshToken.mockReturnValue('refresh-xyz')
    getPlatformToken.mockReturnValue('access-old')
    shouldRefreshToken.mockReturnValue(true)
    refreshSession.mockResolvedValue('new-access')

    renderHook(() => useServiceWorkerAuthBridge({ enabled: true }))

    fireSwMessage({ type: 'AUTH_REQUIRED', status: 401 })
    await Promise.resolve()
    await Promise.resolve()

    expect(refreshSession).toHaveBeenCalledOnce()
  })

  it('does nothing when there is no refresh token', async () => {
    getPlatformRefreshToken.mockReturnValue(null)

    renderHook(() => useServiceWorkerAuthBridge({ enabled: true }))

    fireSwMessage({ type: 'AUTH_REQUIRED', status: 401 })

    expect(refreshSession).not.toHaveBeenCalled()
  })

  it('does nothing when the access token is still fresh (probable stale SW cache)', async () => {
    getPlatformRefreshToken.mockReturnValue('refresh-xyz')
    getPlatformToken.mockReturnValue('access-fresh')
    shouldRefreshToken.mockReturnValue(false)

    renderHook(() => useServiceWorkerAuthBridge({ enabled: true }))

    fireSwMessage({ type: 'AUTH_REQUIRED', status: 401 })

    expect(refreshSession).not.toHaveBeenCalled()
  })

  it('coalesces overlapping AUTH_REQUIRED messages into a single refresh', async () => {
    getPlatformRefreshToken.mockReturnValue('refresh-xyz')
    getPlatformToken.mockReturnValue('access-old')
    shouldRefreshToken.mockReturnValue(true)
    let resolve!: (value: string | null) => void
    refreshSession.mockReturnValue(
      new Promise<string | null>((r) => {
        resolve = r
      }),
    )

    renderHook(() => useServiceWorkerAuthBridge({ enabled: true }))

    fireSwMessage({ type: 'AUTH_REQUIRED', status: 401 })
    fireSwMessage({ type: 'AUTH_REQUIRED', status: 403 })
    fireSwMessage({ type: 'AUTH_REQUIRED', status: 401 })

    expect(refreshSession).toHaveBeenCalledOnce()
    resolve('new-access')
  })

  it('ignores non-AUTH_REQUIRED messages', async () => {
    getPlatformRefreshToken.mockReturnValue('refresh-xyz')
    shouldRefreshToken.mockReturnValue(true)

    renderHook(() => useServiceWorkerAuthBridge({ enabled: true }))

    fireSwMessage({ type: 'CACHE_UPDATED' })
    fireSwMessage('not-an-object')
    fireSwMessage(null)

    expect(refreshSession).not.toHaveBeenCalled()
  })

  it('does not register a listener when disabled', () => {
    renderHook(() => useServiceWorkerAuthBridge({ enabled: false }))

    expect(messageListener).toBeNull()
  })
})
