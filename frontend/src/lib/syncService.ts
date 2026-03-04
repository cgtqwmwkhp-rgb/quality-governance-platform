/**
 * Offline sync service — periodically flushes pending records from IndexedDB
 * to the backend API when the browser is online.
 */

import api from '../api/client'

const DB_NAME = 'qgp-offline'
const STORE_NAME = 'pending-sync'
const MAX_RETRIES = 5

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
  if (!navigator.onLine) return

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
      await deleteRecord(rec.id)
    } catch {
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

  const onOnline = () => flushPending().catch(() => {})
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
