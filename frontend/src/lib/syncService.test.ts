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

  it('skips flush while offline and retries on online event', async () => {
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
    await flushMicrotasks(10)

    expect(apiRequest).not.toHaveBeenCalled()
    expect(records.has('r2')).toBe(true)

    Object.defineProperty(navigator, 'onLine', {
      configurable: true,
      value: true,
    })
    window.dispatchEvent(new Event('online'))
    await flushMicrotasks(20)

    expect(apiRequest).toHaveBeenCalledWith({
      url: '/api/v1/incidents',
      method: 'PUT',
      data: { id: 2 },
    })
    expect(records.has('r2')).toBe(false)

    stop()
  })

  it('increments retries when API flush fails', async () => {
    records.set('r3', {
      id: 'r3',
      url: '/api/v1/complaints',
      method: 'POST',
      body: { subject: 'Retry me' },
      retries: 0,
      createdAt: '2026-07-13T00:00:00.000Z',
    })
    apiRequest.mockRejectedValueOnce(new Error('network down'))

    const { startAutoSync } = await import('./syncService')
    const stop = startAutoSync(60_000)
    await flushMicrotasks(20)

    expect(records.get('r3')?.retries).toBe(1)
    stop()
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
