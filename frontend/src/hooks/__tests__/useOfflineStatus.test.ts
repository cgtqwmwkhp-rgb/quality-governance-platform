import { act, renderHook, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { offlineStorage, useOfflineEntity, useOfflineStatus } from '../../services/offlineStorage'

describe('useOfflineStatus', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    Object.defineProperty(navigator, 'onLine', { configurable: true, value: true })
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('initializes from navigator.onLine and loads pending sync count', async () => {
    vi.spyOn(offlineStorage, 'getSyncQueueCount').mockResolvedValue(4)
    const unsubscribe = vi.fn()
    vi.spyOn(offlineStorage, 'onSyncStatus').mockImplementation((callback) => {
      callback({ status: 'online', pending: 4 })
      return unsubscribe
    })

    const { result, unmount } = renderHook(() => useOfflineStatus())

    await waitFor(() => {
      expect(result.current.pending).toBe(4)
    })
    expect(result.current.status).toBe('online')
    expect(offlineStorage.getSyncQueueCount).toHaveBeenCalledTimes(1)

    unmount()
    expect(unsubscribe).toHaveBeenCalledTimes(1)
  })

  it('reflects offline navigator state before sync callbacks arrive', async () => {
    Object.defineProperty(navigator, 'onLine', { configurable: true, value: false })
    vi.spyOn(offlineStorage, 'getSyncQueueCount').mockResolvedValue(0)
    vi.spyOn(offlineStorage, 'onSyncStatus').mockReturnValue(vi.fn())

    const { result } = renderHook(() => useOfflineStatus())

    await waitFor(() => {
      expect(result.current.status).toBe('offline')
    })
  })

  it('updates when offlineStorage publishes sync status changes', async () => {
    vi.spyOn(offlineStorage, 'getSyncQueueCount').mockResolvedValue(2)
    let listener: ((status: { status: string; pending: number }) => void) | undefined
    vi.spyOn(offlineStorage, 'onSyncStatus').mockImplementation((callback) => {
      listener = callback
      return vi.fn()
    })

    const { result } = renderHook(() => useOfflineStatus())

    await waitFor(() => {
      expect(result.current.pending).toBe(2)
    })

    act(() => {
      listener?.({ status: 'syncing', pending: 1 })
    })
    expect(result.current.status).toBe('syncing')
    expect(result.current.pending).toBe(1)
  })
})

describe('useOfflineEntity', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    localStorage.clear()
    sessionStorage.clear()
    Object.defineProperty(navigator, 'onLine', { configurable: true, value: true })
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('returns cached entity when offline', async () => {
    Object.defineProperty(navigator, 'onLine', { configurable: true, value: false })
    vi.spyOn(offlineStorage, 'getEntity').mockResolvedValue({ id: '42', title: 'Cached audit' })

    const { result } = renderHook(() => useOfflineEntity<{ id: string; title: string }>('audits', '42'))

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false)
    })
    expect(result.current.data).toEqual({ id: '42', title: 'Cached audit' })
    expect(result.current.isFromCache).toBe(true)
  })

  it('refreshes from network when online and updates cache', async () => {
    vi.spyOn(offlineStorage, 'getEntity').mockResolvedValue({ id: '7', title: 'Stale' })
    vi.spyOn(offlineStorage, 'saveEntity').mockResolvedValue(undefined)
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ id: '7', title: 'Fresh' }),
    })
    vi.stubGlobal('fetch', fetchMock)
    localStorage.setItem('access_token', 'test-token')

    const { result } = renderHook(() => useOfflineEntity<{ id: string; title: string }>('audits', '7'))

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false)
    })

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/audits/7'),
      expect.objectContaining({
        headers: { Authorization: 'Bearer test-token' },
      }),
    )
    expect(result.current.data).toEqual({ id: '7', title: 'Fresh' })
    expect(result.current.isFromCache).toBe(false)
    expect(offlineStorage.saveEntity).toHaveBeenCalledWith('audits', { id: '7', title: 'Fresh' })
  })

  it('keeps cached data when network fetch fails', async () => {
    vi.spyOn(offlineStorage, 'getEntity').mockResolvedValue({ id: '9', title: 'Cached only' })
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('network down')))

    const { result } = renderHook(() => useOfflineEntity<{ id: string; title: string }>('audits', '9'))

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false)
    })

    expect(result.current.data).toEqual({ id: '9', title: 'Cached only' })
    expect(result.current.isFromCache).toBe(true)
  })
})
