import { describe, it, expect, beforeEach, beforeAll, vi } from 'vitest'

// Stub the `indexedDB` global so the `isIndexedDbAvailable()` guard inside
// auditDraftStore.ts evaluates to true. The actual underlying IndexedDB
// implementation is irrelevant because we mock the `idb` package below.
beforeAll(() => {
  if (typeof (globalThis as { indexedDB?: unknown }).indexedDB === 'undefined') {
    vi.stubGlobal('indexedDB', { open: () => ({}) } as unknown as IDBFactory)
  }
})

// Minimal in-memory `idb` mock — exposes the same async surface
// (`openDB`, `put`, `get`, `delete`, `getAll`) but stores values in a Map.
// Lets us exercise the snapshot registry + flush flow without IndexedDB.
const stores = new Map<string, Map<unknown, unknown>>()

vi.mock('idb', () => {
  return {
    openDB: vi.fn(async (name: string, _version: number, opts?: { upgrade?: (db: unknown) => void }) => {
      if (!stores.has(name)) stores.set(name, new Map())
      const store = stores.get(name)!
      const fakeDb = {
        objectStoreNames: { contains: () => true },
        createObjectStore: () => ({}),
      }
      opts?.upgrade?.(fakeDb)
      return {
        put: async (_storeName: string, value: { runId: number }) => {
          store.set(value.runId, value)
        },
        get: async (_storeName: string, key: unknown) => store.get(key),
        delete: async (_storeName: string, key: unknown) => {
          store.delete(key)
        },
        getAll: async () => Array.from(store.values()),
      }
    }),
  }
})

import {
  saveAuditDraft,
  getAuditDraft,
  deleteAuditDraft,
  registerDraftSnapshot,
  flushAllDraftsToIndexedDb,
  type AuditDraft,
} from '../auditDraftStore'

function makeDraft(overrides: Partial<AuditDraft> = {}): AuditDraft {
  return {
    runId: 42,
    responses: { q1: { questionId: 'q1', response: 'yes', timestamp: '2026-04-07T00:00:00Z' } },
    responseIdMap: { q1: 100 },
    currentSectionIndex: 0,
    currentQuestionIndex: 0,
    savedAt: 1_700_000_000_000,
    reason: 'autosave',
    ...overrides,
  }
}

// Clear stored data IN PLACE: auditDraftStore caches its `dbPromise` at the
// module level, so the closures returned by our mock `openDB` keep a stable
// reference to the FIRST Map we hand them. Replacing the map (via
// `stores.clear()`) would orphan that reference; we have to clear contents
// of every existing map.
function resetStores() {
  for (const m of stores.values()) m.clear()
}

describe('auditDraftStore — IndexedDB CRUD', () => {
  beforeEach(() => {
    resetStores()
  })

  it('saves and retrieves a draft by runId', async () => {
    const draft = makeDraft()
    await saveAuditDraft(draft)
    const fetched = await getAuditDraft(42)
    expect(fetched).toEqual(draft)
  })

  it('returns null when no draft exists for the runId', async () => {
    const fetched = await getAuditDraft(999)
    expect(fetched).toBeNull()
  })

  it('overwrites an existing draft for the same runId', async () => {
    await saveAuditDraft(makeDraft({ savedAt: 1 }))
    await saveAuditDraft(makeDraft({ savedAt: 2, reason: 'auth-loss' }))
    const fetched = await getAuditDraft(42)
    expect(fetched?.savedAt).toBe(2)
    expect(fetched?.reason).toBe('auth-loss')
  })

  it('deletes a draft', async () => {
    await saveAuditDraft(makeDraft())
    await deleteAuditDraft(42)
    expect(await getAuditDraft(42)).toBeNull()
  })
})

describe('auditDraftStore — snapshot registry', () => {
  beforeEach(() => {
    resetStores()
  })

  it('flushes registered snapshots to IndexedDB on auth-loss', async () => {
    const provider = vi.fn(() => makeDraft({ runId: 7 }))
    const unregister = registerDraftSnapshot(7, provider)

    await flushAllDraftsToIndexedDb('auth-loss')

    expect(provider).toHaveBeenCalledOnce()
    const stashed = await getAuditDraft(7)
    expect(stashed?.runId).toBe(7)
    expect(stashed?.reason).toBe('auth-loss')
    unregister()
  })

  it('skips snapshots whose responses map is empty', async () => {
    const provider = vi.fn(() => makeDraft({ runId: 8, responses: {} }))
    const unregister = registerDraftSnapshot(8, provider)

    await flushAllDraftsToIndexedDb()

    expect(provider).toHaveBeenCalledOnce()
    expect(await getAuditDraft(8)).toBeNull()
    unregister()
  })

  it('treats null providers as no-ops', async () => {
    const provider = vi.fn(() => null)
    const unregister = registerDraftSnapshot(9, provider)

    await flushAllDraftsToIndexedDb()

    expect(provider).toHaveBeenCalledOnce()
    expect(await getAuditDraft(9)).toBeNull()
    unregister()
  })

  it('does not let a throwing provider stop the others', async () => {
    const bad = vi.fn(() => {
      throw new Error('boom')
    })
    const good = vi.fn(() => makeDraft({ runId: 11 }))
    const unregisterBad = registerDraftSnapshot(10, bad)
    const unregisterGood = registerDraftSnapshot(11, good)

    await flushAllDraftsToIndexedDb()

    expect(bad).toHaveBeenCalledOnce()
    expect(good).toHaveBeenCalledOnce()
    expect(await getAuditDraft(11)).not.toBeNull()
    unregisterBad()
    unregisterGood()
  })

  it('unregister removes the provider so it is no longer invoked', async () => {
    const provider = vi.fn(() => makeDraft({ runId: 12 }))
    const unregister = registerDraftSnapshot(12, provider)
    unregister()

    await flushAllDraftsToIndexedDb()

    expect(provider).not.toHaveBeenCalled()
  })

  it('is a no-op when nothing is registered', async () => {
    await expect(flushAllDraftsToIndexedDb()).resolves.toBeUndefined()
  })
})
