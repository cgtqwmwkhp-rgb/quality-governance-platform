import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'

/**
 * Preferred S15 refill — Vitest coverage for OfflineStorage IndexedDB paths.
 * NEW file only; does not re-cover useOfflineStatus / useOfflineEntity hooks.
 */

beforeAll(() => {
  if (typeof (globalThis as { indexedDB?: unknown }).indexedDB === 'undefined') {
    vi.stubGlobal('indexedDB', { open: () => ({}) } as unknown as IDBFactory)
  }
})

type StoreMap = Map<string, Map<IDBValidKey, unknown>>

const dbStores: StoreMap = new Map()

function ensureStore(name: string): Map<IDBValidKey, unknown> {
  if (!dbStores.has(name)) dbStores.set(name, new Map())
  return dbStores.get(name)!
}

function resetStores() {
  for (const store of dbStores.values()) store.clear()
}

vi.mock('idb', () => {
  return {
    openDB: vi.fn(async (_name: string, _version: number, opts?: { upgrade?: (db: unknown) => void }) => {
      const fakeDb = {
        objectStoreNames: {
          contains: (storeName: string) => dbStores.has(storeName),
        },
        createObjectStore: (storeName: string) => {
          ensureStore(storeName)
          return {
            createIndex: () => undefined,
          }
        },
      }
      opts?.upgrade?.(fakeDb)

      return {
        put: async (storeName: string, value: { id?: string; key?: string }) => {
          const store = ensureStore(storeName)
          const key = (value.id ?? value.key) as IDBValidKey
          store.set(key, value)
        },
        get: async (storeName: string, key: IDBValidKey) => {
          return ensureStore(storeName).get(key)
        },
        delete: async (storeName: string, key: IDBValidKey) => {
          ensureStore(storeName).delete(key)
        },
        clear: async (storeName: string) => {
          ensureStore(storeName).clear()
        },
        count: async (storeName: string) => ensureStore(storeName).size,
        getAll: async (storeName: string) => Array.from(ensureStore(storeName).values()),
        getAllFromIndex: async (storeName: string, _indexName: string) => {
          const values = Array.from(ensureStore(storeName).values()) as Array<{ timestamp?: number }>
          return values.sort((a, b) => (a.timestamp ?? 0) - (b.timestamp ?? 0))
        },
        transaction: (storeName: string, _mode?: string) => {
          const store = ensureStore(storeName)
          return {
            store: {
              put: async (value: { id: string }) => {
                store.set(value.id, value)
              },
            },
            done: Promise.resolve(),
          }
        },
      }
    }),
  }
})

vi.mock('../../config/apiBase', () => ({
  API_BASE_URL: 'https://api.test/v1',
}))

import { offlineStorage } from '../offlineStorage'

describe('offlineStorage — sync queue', () => {
  beforeEach(() => {
    resetStores()
    vi.restoreAllMocks()
    Object.defineProperty(navigator, 'onLine', { configurable: true, value: false })
    window.dispatchEvent(new Event('offline'))
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('addToSyncQueue persists a pending item with retryCount 0 while offline', async () => {
    const id = await offlineStorage.addToSyncQueue({
      operation: 'create',
      entityType: 'incidents',
      entityId: 'inc-1',
      data: { title: 'Near miss' },
    })

    expect(id).toMatch(/^sync_/)
    expect(await offlineStorage.getSyncQueueCount()).toBe(1)

    const queue = await offlineStorage.getSyncQueue()
    expect(queue).toHaveLength(1)
    expect(queue[0]).toMatchObject({
      id,
      operation: 'create',
      entityType: 'incidents',
      entityId: 'inc-1',
      retryCount: 0,
      data: { title: 'Near miss' },
    })
  })

  it('removeFromSyncQueue deletes the pending item', async () => {
    const id = await offlineStorage.addToSyncQueue({
      operation: 'update',
      entityType: 'audits',
      entityId: 'aud-9',
      data: { status: 'open' },
    })

    await offlineStorage.removeFromSyncQueue(id)
    expect(await offlineStorage.getSyncQueueCount()).toBe(0)
    expect(await offlineStorage.getSyncQueue()).toEqual([])
  })
})

describe('offlineStorage — cache', () => {
  beforeEach(() => {
    resetStores()
    Object.defineProperty(navigator, 'onLine', { configurable: true, value: false })
    window.dispatchEvent(new Event('offline'))
  })

  it('cacheSet / cacheGet round-trip', async () => {
    await offlineStorage.cacheSet('incident:1', { id: '1', title: 'Cached' })
    expect(await offlineStorage.cacheGet('incident:1')).toEqual({ id: '1', title: 'Cached' })
  })

  it('cacheGet returns null for missing and expired keys', async () => {
    expect(await offlineStorage.cacheGet('missing')).toBeNull()

    const now = 1_700_000_000_000
    vi.spyOn(Date, 'now').mockReturnValue(now)
    await offlineStorage.cacheSet('ttl-key', { v: 1 }, 1)

    vi.spyOn(Date, 'now').mockReturnValue(now + 2_000)
    expect(await offlineStorage.cacheGet('ttl-key')).toBeNull()
  })

  it('cacheDelete and cacheClear remove entries', async () => {
    await offlineStorage.cacheSet('a', 1)
    await offlineStorage.cacheSet('b', 2)
    await offlineStorage.cacheDelete('a')
    expect(await offlineStorage.cacheGet('a')).toBeNull()
    expect(await offlineStorage.cacheGet('b')).toBe(2)

    await offlineStorage.cacheClear()
    expect(await offlineStorage.cacheGet('b')).toBeNull()
  })
})

describe('offlineStorage — entities + settings + uploads', () => {
  beforeEach(() => {
    resetStores()
    Object.defineProperty(navigator, 'onLine', { configurable: true, value: false })
    window.dispatchEvent(new Event('offline'))
  })

  it('saveEntity / getEntity / getAllEntities / deleteEntity for incidents', async () => {
    await offlineStorage.saveEntity('incidents', { id: 'i1', title: 'A', updated_at: 1 })
    await offlineStorage.saveEntities('incidents', [
      { id: 'i2', title: 'B', updated_at: 2 },
      { id: 'i3', title: 'C', updated_at: 3 },
    ])

    expect(await offlineStorage.getEntity('incidents', 'i1')).toEqual({
      id: 'i1',
      title: 'A',
      updated_at: 1,
    })
    const all = await offlineStorage.getAllEntities('incidents')
    expect(all).toHaveLength(3)

    await offlineStorage.deleteEntity('incidents', 'i2')
    expect(await offlineStorage.getEntity('incidents', 'i2')).toBeUndefined()
    expect(await offlineStorage.getAllEntities('incidents')).toHaveLength(2)
  })

  it('ignores unknown entity types for get/save', async () => {
    await offlineStorage.saveEntity('syncQueue' as never, { id: 'x' })
    expect(await offlineStorage.getEntity('syncQueue' as never, 'x')).toBeNull()
    expect(await offlineStorage.getAllEntities('userSettings' as never)).toEqual([])
  })

  it('setSetting / getSetting round-trip', async () => {
    await offlineStorage.setSetting('theme', { mode: 'dark' })
    expect(await offlineStorage.getSetting('theme')).toEqual({ key: 'theme', mode: 'dark' })
    expect(await offlineStorage.getSetting('missing')).toBeNull()
  })

  it('queueUpload / getPendingUploads / removeUpload', async () => {
    const file = new File(['evidence'], 'photo.jpg', { type: 'image/jpeg' })
    const id = await offlineStorage.queueUpload(file, { entityId: 'inc-1' })
    expect(id).toMatch(/^upload_/)

    const pending = await offlineStorage.getPendingUploads()
    expect(pending).toHaveLength(1)
    expect(pending[0]).toMatchObject({ id, metadata: { entityId: 'inc-1' } })

    await offlineStorage.removeUpload(id)
    expect(await offlineStorage.getPendingUploads()).toEqual([])
  })
})

describe('offlineStorage — processQueue + online status', () => {
  beforeEach(() => {
    resetStores()
    vi.restoreAllMocks()
    Object.defineProperty(navigator, 'onLine', { configurable: true, value: false })
    window.dispatchEvent(new Event('offline'))
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('processQueue is a no-op while offline', async () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)

    await offlineStorage.addToSyncQueue({
      operation: 'create',
      entityType: 'incidents',
      entityId: 'inc-1',
      data: { title: 'Queued' },
    })

    await offlineStorage.processQueue()
    expect(fetchMock).not.toHaveBeenCalled()
    expect(await offlineStorage.getSyncQueueCount()).toBe(1)
  })

  it('processQueue flushes create items via API when online and removes them', async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 200, statusText: 'OK' })
    vi.stubGlobal('fetch', fetchMock)
    localStorage.setItem('access_token', 'tok-123')

    await offlineStorage.addToSyncQueue({
      operation: 'create',
      entityType: 'incidents',
      entityId: 'inc-1',
      data: { title: 'Flush me' },
    })

    Object.defineProperty(navigator, 'onLine', { configurable: true, value: true })
    window.dispatchEvent(new Event('online'))
    // online listener also kicks processQueue; wait for both paths to settle
    await vi.waitFor(async () => {
      expect(await offlineStorage.getSyncQueueCount()).toBe(0)
    })

    expect(fetchMock).toHaveBeenCalled()
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('https://api.test/v1/incidents')
    expect(init).toMatchObject({
      method: 'POST',
      headers: expect.objectContaining({
        Authorization: 'Bearer tok-123',
      }),
    })
  })

  it('processQueue increments retryCount on API failure and keeps the item', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      statusText: 'Server Error',
    })
    vi.stubGlobal('fetch', fetchMock)

    await offlineStorage.addToSyncQueue({
      operation: 'update',
      entityType: 'risks',
      entityId: 'r-1',
      data: { score: 9 },
    })

    Object.defineProperty(navigator, 'onLine', { configurable: true, value: true })
    // Call processQueue directly (avoid double-run from online event race)
    // Force online flag via event, then wait a tick for listener; if queue already
    // processing from the event, waitFor still converges.
    window.dispatchEvent(new Event('online'))

    await vi.waitFor(async () => {
      const queue = await offlineStorage.getSyncQueue()
      expect(queue[0]?.retryCount).toBeGreaterThanOrEqual(1)
    })

    const queue = await offlineStorage.getSyncQueue()
    expect(queue).toHaveLength(1)
    expect(queue[0].lastError).toMatch(/Sync failed: 500/)
    expect(fetchMock).toHaveBeenCalled()
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('https://api.test/v1/risks/r-1')
    expect(init.method).toBe('PATCH')
  })

  it('getOnlineStatus and onSyncStatus reflect online/offline transitions', async () => {
    const statuses: Array<{ status: string; pending: number }> = []
    const unsubscribe = offlineStorage.onSyncStatus((s) => statuses.push({ ...s }))

    window.dispatchEvent(new Event('offline'))
    expect(offlineStorage.getOnlineStatus()).toBe(false)
    expect(statuses.at(-1)?.status).toBe('offline')

    window.dispatchEvent(new Event('online'))
    expect(offlineStorage.getOnlineStatus()).toBe(true)
    expect(statuses.some((s) => s.status === 'online')).toBe(true)

    unsubscribe()
    const before = statuses.length
    window.dispatchEvent(new Event('offline'))
    expect(statuses.length).toBe(before)
  })
})
