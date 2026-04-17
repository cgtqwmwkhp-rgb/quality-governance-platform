/**
 * auditDraftStore
 *
 * Lightweight IndexedDB-backed stash for in-flight audit responses.
 *
 * Why a dedicated tiny DB instead of extending offlineStorage.ts?
 *   - Zero migration risk for the existing v1 `quality-governance-offline`
 *     database (no version bump, no upgrade path to test on user devices).
 *   - Independent failure mode: if this store is corrupt or evicted, normal
 *     audit save / submit still works against the API.
 *   - Cheap to reason about: one store, three operations.
 *
 * Use:
 *   - `saveAuditDraft(runId, draft)` is called by the periodic autosave fallback
 *     and by the auth-loss "soft recovery" hook in api/client.ts.
 *   - `getAuditDraft(runId)` is called when AuditExecution mounts so we can
 *     offer to restore unsaved local answers if the user was logged out
 *     mid-audit.
 *   - `deleteAuditDraft(runId)` is called once a server-side save succeeds
 *     so we don't keep stale drafts hanging around.
 */
import { openDB, type IDBPDatabase, type DBSchema } from 'idb'

const DB_NAME = 'qgp-audit-drafts'
const DB_VERSION = 1
const STORE = 'drafts'

export interface AuditDraftQuestion {
  questionId: string
  response: unknown
  notes?: string
  photos?: string[]
  signature?: string
  flagged?: boolean
  timestamp: string
  duration?: number
}

export interface AuditDraft {
  runId: number
  responses: Record<string, AuditDraftQuestion>
  responseIdMap: Record<string, number>
  currentSectionIndex: number
  currentQuestionIndex: number
  savedAt: number
  reason: 'autosave' | 'auth-loss' | 'manual'
}

interface AuditDraftSchema extends DBSchema {
  drafts: {
    key: number
    value: AuditDraft
  }
}

let dbPromise: Promise<IDBPDatabase<AuditDraftSchema>> | null = null

function isIndexedDbAvailable(): boolean {
  try {
    return (
      typeof indexedDB !== 'undefined' &&
      indexedDB !== null &&
      typeof (indexedDB as IDBFactory).open === 'function'
    )
  } catch {
    return false
  }
}

async function getDb(): Promise<IDBPDatabase<AuditDraftSchema> | null> {
  if (!isIndexedDbAvailable()) return null
  if (!dbPromise) {
    dbPromise = openDB<AuditDraftSchema>(DB_NAME, DB_VERSION, {
      upgrade(db) {
        if (!db.objectStoreNames.contains(STORE)) {
          db.createObjectStore(STORE, { keyPath: 'runId' })
        }
      },
    })
  }
  try {
    return await dbPromise
  } catch {
    dbPromise = null
    return null
  }
}

export async function saveAuditDraft(draft: AuditDraft): Promise<boolean> {
  const db = await getDb()
  if (!db) return false
  try {
    await db.put(STORE, draft)
    return true
  } catch {
    return false
  }
}

export async function getAuditDraft(runId: number): Promise<AuditDraft | null> {
  const db = await getDb()
  if (!db) return null
  try {
    return (await db.get(STORE, runId)) ?? null
  } catch {
    return null
  }
}

export async function deleteAuditDraft(runId: number): Promise<void> {
  const db = await getDb()
  if (!db) return
  try {
    await db.delete(STORE, runId)
  } catch {
    /* swallow */
  }
}

export async function listAuditDrafts(): Promise<AuditDraft[]> {
  const db = await getDb()
  if (!db) return []
  try {
    return await db.getAll(STORE)
  } catch {
    return []
  }
}

// ---------------------------------------------------------------------------
// In-memory snapshot registry
// ---------------------------------------------------------------------------
// AuditExecution registers a snapshot function on mount; api/client.ts calls
// every registered snapshot just before any auth-loss redirect so unsaved
// answers get stashed in IndexedDB before the page navigates away.
// This keeps the audit page decoupled from the auth client (it never has to
// know about clearTokens itself).

type DraftSnapshot = () => AuditDraft | null
const snapshotProviders = new Map<number, DraftSnapshot>()

export function registerDraftSnapshot(runId: number, provider: DraftSnapshot): () => void {
  snapshotProviders.set(runId, provider)
  return () => {
    if (snapshotProviders.get(runId) === provider) {
      snapshotProviders.delete(runId)
    }
  }
}

/**
 * Synchronously collect every registered draft snapshot, then asynchronously
 * write them to IndexedDB. Returns a promise that resolves when the writes
 * complete (or immediately for callers that can't `await`).
 *
 * Used by api/client.ts on the auth-loss redirect path: callers should kick
 * this off but should NOT block the redirect on it (browsers throttle JS
 * before navigation, but `idb` writes are typically <50ms).
 */
export function flushAllDraftsToIndexedDb(reason: AuditDraft['reason'] = 'auth-loss'): Promise<void> {
  const drafts: AuditDraft[] = []
  for (const provider of snapshotProviders.values()) {
    try {
      const snap = provider()
      if (snap && Object.keys(snap.responses).length > 0) {
        drafts.push({ ...snap, reason, savedAt: Date.now() })
      }
    } catch {
      /* one bad provider mustn't stop the others */
    }
  }
  if (drafts.length === 0) return Promise.resolve()
  return Promise.all(drafts.map((d) => saveAuditDraft(d))).then(() => undefined)
}
