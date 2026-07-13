import { act, renderHook, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useServiceWorker } from '../useServiceWorker'

function installServiceWorkerSupport(options?: {
  registerImpl?: () => Promise<ServiceWorkerRegistration>
  onLine?: boolean
}) {
  const pushSubscription = {
    unsubscribe: vi.fn().mockResolvedValue(true),
  }

  const registration = {
    scope: '/',
    installing: null,
    waiting: null,
    addEventListener: vi.fn(),
    update: vi.fn().mockResolvedValue(undefined),
    pushManager: {
      getSubscription: vi.fn().mockResolvedValue(pushSubscription),
      subscribe: vi.fn(),
    },
  } as unknown as ServiceWorkerRegistration

  Object.defineProperty(navigator, 'onLine', {
    configurable: true,
    value: options?.onLine ?? true,
  })

  Object.defineProperty(navigator, 'serviceWorker', {
    configurable: true,
    value: {
      register: vi
        .fn()
        .mockImplementation(
          options?.registerImpl ?? (() => Promise.resolve(registration)),
        ),
      controller: null,
    },
  })

  // @ts-expect-error test shim for PushManager presence check
  globalThis.PushManager = class PushManager {}

  return { registration, pushSubscription }
}

function removeServiceWorkerSupport() {
  // @ts-expect-error cleanup test shim
  delete globalThis.PushManager
  Object.defineProperty(navigator, 'serviceWorker', {
    configurable: true,
    value: undefined,
  })
}

describe('useServiceWorker', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  afterEach(() => {
    removeServiceWorkerSupport()
  })

  it('reports unsupported when serviceWorker is unavailable', async () => {
    removeServiceWorkerSupport()

    const { result } = renderHook(() => useServiceWorker())

    await waitFor(() => {
      expect(result.current.isSupported).toBe(false)
    })
    expect(result.current.isRegistered).toBe(false)
  })

  it('detects support and auto-registers on mount', async () => {
    installServiceWorkerSupport()

    const { result } = renderHook(() => useServiceWorker())

    await waitFor(() => {
      expect(result.current.isSupported).toBe(true)
    })

    await waitFor(() => {
      expect(result.current.isRegistered).toBe(true)
    })

    expect(navigator.serviceWorker.register).toHaveBeenCalledWith('/sw.js', { scope: '/' })
  })

  it('reflects navigator.onLine and reacts to online/offline events', async () => {
    installServiceWorkerSupport({ onLine: true })

    const { result } = renderHook(() => useServiceWorker())

    await waitFor(() => {
      expect(result.current.isOnline).toBe(true)
    })

    act(() => {
      Object.defineProperty(navigator, 'onLine', { configurable: true, value: false })
      window.dispatchEvent(new Event('offline'))
    })

    expect(result.current.isOnline).toBe(false)

    act(() => {
      Object.defineProperty(navigator, 'onLine', { configurable: true, value: true })
      window.dispatchEvent(new Event('online'))
    })

    expect(result.current.isOnline).toBe(true)
  })

  it('registerSW is a no-op when service workers are unsupported', async () => {
    removeServiceWorkerSupport()

    const { result } = renderHook(() => useServiceWorker())

    await act(async () => {
      await result.current.registerSW()
    })

    expect(result.current.isRegistered).toBe(false)
  })

  it('unsubscribeFromPush returns false when there is no subscription', async () => {
    installServiceWorkerSupport()

    const { result } = renderHook(() => useServiceWorker())

    let unsubscribed = false
    await act(async () => {
      unsubscribed = await result.current.unsubscribeFromPush()
    })

    expect(unsubscribed).toBe(false)
  })

  it('unsubscribeFromPush clears an active subscription', async () => {
    const { pushSubscription } = installServiceWorkerSupport()

    const { result } = renderHook(() => useServiceWorker())

    await waitFor(() => {
      expect(result.current.isRegistered).toBe(true)
    })

    await waitFor(() => {
      expect(result.current.pushSubscription).not.toBeNull()
    })

    let unsubscribed = false
    await act(async () => {
      unsubscribed = await result.current.unsubscribeFromPush()
    })

    expect(unsubscribed).toBe(true)
    expect(pushSubscription.unsubscribe).toHaveBeenCalledOnce()
    expect(result.current.pushSubscription).toBeNull()
  })

  it('syncPendingReports is safe when background sync is unavailable', async () => {
    installServiceWorkerSupport()

    const { result } = renderHook(() => useServiceWorker())

    await waitFor(() => {
      expect(result.current.isRegistered).toBe(true)
    })

    await act(async () => {
      await result.current.syncPendingReports()
    })

    expect(result.current.registration).not.toBeNull()
  })
})
