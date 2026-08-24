/**
 * Offline sync service — periodically flushes pending records from IndexedDB
 * to the backend API.
 *
 * Connectivity model (PX-128): `navigator.onLine` is a hint, not a fact. It
 * reports false on captive portals, VPN flaps and some Android WebViews while
 * requests are in fact succeeding, and it never fires an `online` event to
 * correct itself. Gating the flush on it meant queued writes could sit
 * unsent indefinitely while GETs on the same connection worked fine.
 *
 * So the queue drain is itself the connectivity probe: we attempt it on a
 * timer regardless of what the browser claims, and back off exponentially
 * only after a request actually fails at the network layer. Any successful
 * API response — from the drain or from a normal call elsewhere in the app —
 * is proof of connectivity and clears the backoff.
 */

import api from '../api/client'

const DB_NAME = 'qgp-offline'
const STORE_NAME = 'pending-sync'
const MAX_RETRIES = 5

const BACKOFF_BASE_MS = 30_000
const BACKOFF_MAX_MS = 5 * 60 * 1000

let consecutiveNetworkFailures = 0
let nextAttemptAfterMs = 0

/**
 * Record that the network is demonstrably reachable, so the queue should be
 * drained at the next opportunity.
 *
 * Called on every successful queued write and by the fetch-based API service.
 * It only clears the backoff rather than draining inline: a drain opens
 * IndexedDB and walks the whole queue, which is far too heavy to run on every
 * successful response. The periodic timer picks it up within one interval.
 */
export function reportConnectivityProof(): void {
  consecutiveNetworkFailures = 0
  nextAttemptAfterMs = 0
}

/**
 * A failure with no HTTP response never reached the server, so it says
 * nothing about whether the request was valid. Treated as a connectivity
 * problem: back off, but do not spend the record's retry budget.
 */
function isNetworkError(error: unknown): boolean {
  if (!error || typeof error !== 'object') return true
  const response = (error as { response?: unknown }).response
  return response === undefined || response === null
}

function registerNetworkFailure(): void {
  consecutiveNetworkFailures += 1
  const delay = Math.min(
    BACKOFF_MAX_MS,
    BACKOFF_BASE_MS * 2 ** (consecutiveNetworkFailures - 1),
  )
  nextAttemptAfterMs = Date.now() + delay
}

interface PendingRecord {
  id: string
  url: string
  method: 'POST' | 'PUT' | 'PATCH' | 'DELETE'
  body?: unknown
  retries: number
  createdAt: string
}

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, 1)
    req.onupgradeneeded = () => {
      const db = req.result
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        db.createObjectStore(STORE_NAME, { keyPath: 'id' })
      }
    }
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => reject(req.error)
  })
}

async function getAllPending(): Promise<PendingRecord[]> {
  const db = await openDb()
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, 'readonly')
    const store = tx.objectStore(STORE_NAME)
    const req = store.getAll()
    req.onsuccess = () => resolve(req.result ?? [])
    req.onerror = () => reject(req.error)
  })
}

async function deleteRecord(id: string): Promise<void> {
  const db = await openDb()
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, 'readwrite')
    const store = tx.objectStore(STORE_NAME)
    const req = store.delete(id)
    req.onsuccess = () => resolve()
    req.onerror = () => reject(req.error)
  })
}

async function updateRetries(record: PendingRecord): Promise<void> {
  const db = await openDb()
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, 'readwrite')
    const store = tx.objectStore(STORE_NAME)
    const req = store.put({ ...record, retries: record.retries + 1 })
    req.onsuccess = () => resolve()
    req.onerror = () => reject(req.error)
  })
}

async function flushPending(): Promise<void> {
  // Deliberately no `navigator.onLine` gate — see the connectivity model note
  // at the top of this file. The backoff window is the only throttle.
  if (Date.now() < nextAttemptAfterMs) return

  const records = await getAllPending()

  for (const rec of records) {
    if (rec.retries >= MAX_RETRIES) {
      await deleteRecord(rec.id)
      continue
    }

    try {
      await api.request({
        url: rec.url,
        method: rec.method,
        data: rec.body ?? undefined,
      })
      reportConnectivityProof()
      await deleteRecord(rec.id)
    } catch (error) {
      if (isNetworkError(error)) {
        // The connection is down, not the record. Burning retries here would
        // silently delete a field user's queued writes after five offline
        // ticks, so stop the drain and let the backoff run instead.
        registerNetworkFailure()
        return
      }
      await updateRetries(rec)
    }
  }
}

/**
 * Start a periodic sync that flushes pending offline records.
 * Returns a cleanup function to stop the timer.
 */
export function startAutoSync(intervalMs = 30_000): () => void {
  flushPending().catch(() => {})

  const handle = setInterval(() => {
    flushPending().catch(() => {})
  }, intervalMs)

  // The `online` event is a useful nudge when it does fire — it just is not
  // the only way back, and cannot be relied on to fire at all.
  const onOnline = () => {
    reportConnectivityProof()
    flushPending().catch(() => {})
  }
  window.addEventListener('online', onOnline)

  return () => {
    clearInterval(handle)
    window.removeEventListener('online', onOnline)
  }
}

/**
 * Queue a request for later sync when offline.
 */
export async function queueForSync(
  url: string,
  method: PendingRecord['method'],
  body?: unknown,
): Promise<void> {
  const db = await openDb()
  const record: PendingRecord = {
    id: crypto.randomUUID(),
    url,
    method,
    body,
    retries: 0,
    createdAt: new Date().toISOString(),
  }
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, 'readwrite')
    const store = tx.objectStore(STORE_NAME)
    const req = store.put(record)
    req.onsuccess = () => resolve()
    req.onerror = () => reject(req.error)
  })
}
