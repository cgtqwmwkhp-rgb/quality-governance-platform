import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const apiRequest = vi.fn()

vi.mock('../api/client', () => ({
  default: {
    request: (...args: unknown[]) => apiRequest(...args),
  },
}))

type PendingRecord = {
  id: string
  url: string
  method: 'POST' | 'PUT' | 'PATCH' | 'DELETE'
  body?: unknown
  retries: number
  createdAt: string
}

class MemoryIDBRequest<T = unknown> {
  result!: T
  error: DOMException | null = null
  onsuccess: ((this: IDBRequest<T>, ev: Event) => void) | null = null
  onerror: ((this: IDBRequest<T>, ev: Event) => void) | null = null
  onupgradeneeded: ((this: IDBOpenDBRequest, ev: IDBVersionChangeEvent) => void) | null = null

  succeed(value: T) {
    this.result = value
    queueMicrotask(() => {
      this.onsuccess?.call(this as unknown as IDBRequest<T>, new Event('success'))
    })
  }
}

class MemoryObjectStore {
  constructor(private readonly records: Map<string, PendingRecord>) {}

  getAll() {
    const req = new MemoryIDBRequest<PendingRecord[]>()
    req.succeed([...this.records.values()])
    return req as unknown as IDBRequest<PendingRecord[]>
  }

  put(record: PendingRecord) {
    const req = new MemoryIDBRequest<IDBValidKey>()
    this.records.set(record.id, record)
    req.succeed(record.id)
    return req as unknown as IDBRequest<IDBValidKey>
  }

  delete(id: string) {
    const req = new MemoryIDBRequest<undefined>()
    this.records.delete(id)
    req.succeed(undefined)
    return req as unknown as IDBRequest<undefined>
  }
}

class MemoryTransaction {
  constructor(private readonly records: Map<string, PendingRecord>) {}

  objectStore(_name: string) {
    return new MemoryObjectStore(this.records) as unknown as IDBObjectStore
  }
}

class MemoryDatabase {
  objectStoreNames = {
    contains: (name: string) => name === 'pending-sync',
  }

  constructor(private readonly records: Map<string, PendingRecord>) {}

  createObjectStore(_name: string, _options?: IDBObjectStoreParameters) {
    return {} as IDBObjectStore
  }

  transaction(_storeName: string, _mode?: IDBTransactionMode) {
    return new MemoryTransaction(this.records) as unknown as IDBTransaction
  }
}

function installIndexedDb(records: Map<string, PendingRecord>) {
  const open = vi.fn((_name: string, _version?: number) => {
    const req = new MemoryIDBRequest<MemoryDatabase>()
    const db = new MemoryDatabase(records)
    // Match real IDB: result is available during upgradeneeded and success.
    req.result = db
    queueMicrotask(() => {
      req.onupgradeneeded?.call(
        req as unknown as IDBOpenDBRequest,
        new Event('upgradeneeded') as IDBVersionChangeEvent,
      )
      req.onsuccess?.call(req as unknown as IDBRequest<MemoryDatabase>, new Event('success'))
    })
    return req as unknown as IDBOpenDBRequest
  })

  vi.stubGlobal('indexedDB', { open } as unknown as IDBFactory)
  return open
}

async function flushMicrotasks(times = 8) {
  for (let i = 0; i < times; i += 1) {
    await Promise.resolve()
  }
}

describe('syncService', () => {
  let records: Map<string, PendingRecord>

  beforeEach(() => {
    vi.resetModules()
    vi.clearAllMocks()
    records = new Map()
    installIndexedDb(records)
    apiRequest.mockResolvedValue({ data: { ok: true } })
    Object.defineProperty(navigator, 'onLine', {
      configurable: true,
      value: true,
    })
    vi.stubGlobal('crypto', {
      randomUUID: vi.fn(() => 'sync-record-1'),
    })
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it('queueForSync persists a pending offline record', async () => {
    const { queueForSync } = await import('./syncService')

    await queueForSync('/api/v1/incidents', 'POST', { title: 'Near miss' })

    expect(records.size).toBe(1)
    const stored = records.get('sync-record-1')
    expect(stored).toMatchObject({
      id: 'sync-record-1',
      url: '/api/v1/incidents',
      method: 'POST',
      body: { title: 'Near miss' },
      retries: 0,
    })
    expect(stored?.createdAt).toEqual(expect.any(String))
  })

  it('startAutoSync flushes queued records when online and cleans up listeners', async () => {
    records.set('r1', {
      id: 'r1',
      url: '/api/v1/complaints',
      method: 'POST',
      body: { subject: 'Noise' },
      retries: 0,
      createdAt: '2026-07-13T00:00:00.000Z',
    })

    const addSpy = vi.spyOn(window, 'addEventListener')
    const removeSpy = vi.spyOn(window, 'removeEventListener')
    const { startAutoSync } = await import('./syncService')

    const stop = startAutoSync(60_000)
    await flushMicrotasks(20)

    expect(apiRequest).toHaveBeenCalledWith({
      url: '/api/v1/complaints',
      method: 'POST',
      data: { subject: 'Noise' },
    })
    expect(records.has('r1')).toBe(false)
    expect(addSpy).toHaveBeenCalledWith('online', expect.any(Function))

    stop()
    expect(removeSpy).toHaveBeenCalledWith('online', expect.any(Function))
  })

  // PX-128: `navigator.onLine` reports false on captive portals and VPN flaps
  // while requests actually succeed, and never fires `online` to correct
  // itself. The previous behaviour — asserted by the test this replaces — was
  // to skip the flush entirely, so queued writes were stranded indefinitely.
  it('drains queued writes even while navigator.onLine reports false', async () => {
    records.set('r2', {
      id: 'r2',
      url: '/api/v1/incidents',
      method: 'PUT',
      body: { id: 2 },
      retries: 1,
      createdAt: '2026-07-13T00:00:00.000Z',
    })

    Object.defineProperty(navigator, 'onLine', {
      configurable: true,
      value: false,
    })

    const { startAutoSync } = await import('./syncService')
    const stop = startAutoSync(60_000)
    await flushMicrotasks(20)

    expect(apiRequest).toHaveBeenCalledWith({
      url: '/api/v1/incidents',
      method: 'PUT',
      data: { id: 2 },
    })
    expect(records.has('r2')).toBe(false)

    stop()
  })

  it('still flushes on the online event when the browser does fire one', async () => {
    const { startAutoSync } = await import('./syncService')
    const stop = startAutoSync(60_000)
    await flushMicrotasks(10)

    records.set('r2b', {
      id: 'r2b',
      url: '/api/v1/incidents',
      method: 'PUT',
      body: { id: 22 },
      retries: 0,
      createdAt: '2026-07-13T00:00:00.000Z',
    })

    window.dispatchEvent(new Event('online'))
    await flushMicrotasks(20)

    expect(records.has('r2b')).toBe(false)
    stop()
  })

  it('increments retries when the server rejects the queued write', async () => {
    records.set('r3', {
      id: 'r3',
      url: '/api/v1/complaints',
      method: 'POST',
      body: { subject: 'Retry me' },
      retries: 0,
      createdAt: '2026-07-13T00:00:00.000Z',
    })
    // An HTTP response means the server saw the request and refused it.
    apiRequest.mockRejectedValueOnce({ response: { status: 422 } })

    const { startAutoSync } = await import('./syncService')
    const stop = startAutoSync(60_000)
    await flushMicrotasks(20)

    expect(records.get('r3')?.retries).toBe(1)
    stop()
  })

  // Without this, fixing the offline gate above would make things worse: an
  // genuinely offline device would burn all five retries in a few ticks and
  // silently delete the user's queued writes.
  it('does not spend the retry budget on a network-layer failure', async () => {
    records.set('r3b', {
      id: 'r3b',
      url: '/api/v1/complaints',
      method: 'POST',
      body: { subject: 'Keep me' },
      retries: 0,
      createdAt: '2026-07-13T00:00:00.000Z',
    })
    // No `response` property: the request never reached the server.
    apiRequest.mockRejectedValue(new Error('network down'))

    const { startAutoSync } = await import('./syncService')
    const stop = startAutoSync(60_000)
    await flushMicrotasks(20)

    expect(records.get('r3b')?.retries).toBe(0)
    expect(records.has('r3b')).toBe(true)
    stop()
  })

  it('backs off after a network failure, and resumes on proof of connectivity', async () => {
    vi.useFakeTimers()
    try {
      records.set('r5', {
        id: 'r5',
        url: '/api/v1/incidents',
        method: 'POST',
        body: { title: 'Backoff' },
        retries: 0,
        createdAt: '2026-07-13T00:00:00.000Z',
      })
      apiRequest.mockRejectedValueOnce(new Error('network down'))

      const { startAutoSync, reportConnectivityProof } = await import('./syncService')
      const stop = startAutoSync(1_000)
      await flushMicrotasks(20)

      expect(apiRequest).toHaveBeenCalledTimes(1)
      expect(records.has('r5')).toBe(true)

      // Well inside the 30s backoff window: the next tick must be a no-op, so
      // an offline device is not hammering the radio every second.
      apiRequest.mockResolvedValue({ data: { ok: true } })
      vi.advanceTimersByTime(1_000)
      await flushMicrotasks(20)
      expect(apiRequest).toHaveBeenCalledTimes(1)

      // A successful response elsewhere in the app is proof we are reachable
      // again — no `online` event required.
      reportConnectivityProof()
      vi.advanceTimersByTime(1_000)
      await flushMicrotasks(20)

      expect(apiRequest).toHaveBeenCalledTimes(2)
      expect(records.has('r5')).toBe(false)
      stop()
    } finally {
      vi.useRealTimers()
    }
  })

  it('drops records that exceeded MAX_RETRIES without calling the API', async () => {
    records.set('r4', {
      id: 'r4',
      url: '/api/v1/incidents',
      method: 'DELETE',
      retries: 5,
      createdAt: '2026-07-13T00:00:00.000Z',
    })

    const { startAutoSync } = await import('./syncService')
    const stop = startAutoSync(60_000)
    await flushMicrotasks(20)

    expect(apiRequest).not.toHaveBeenCalled()
    expect(records.has('r4')).toBe(false)
    stop()
  })
})
