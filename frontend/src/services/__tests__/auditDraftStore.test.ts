/**
 * AUD-F6 — the audit device ledger.
 *
 * Every case here pins a defect that was live on a shared field tablet:
 *
 *  - drafts keyed by `runId` alone, so the next auditor was offered the previous
 *    auditor's answers;
 *  - signing out left them there;
 *  - photos stored as data URLs inside the answer record, rewritten in full on
 *    every 60-second autosave tick;
 *  - `QuotaExceeded` swallowed into `return false`, so a full device looked
 *    exactly like a working one;
 *  - `persist()` never called, so nobody — auditor included — knew whether the
 *    browser intended to keep any of it;
 *  - staff and customer pick-list *names* cached on the device alongside them.
 *
 * The `idb` package is mocked with an in-memory store-per-name map, as the v1
 * suite did. That keeps the real key derivation, the real sanitiser and the real
 * failure classification under test — only the browser's storage engine is
 * substituted — and it lets a put be made to fail on demand, which is the only
 * way to exercise the quota path without filling a real disk.
 */
import { describe, it, expect, beforeEach, beforeAll, vi } from 'vitest'

beforeAll(() => {
  if (typeof (globalThis as { indexedDB?: unknown }).indexedDB === 'undefined') {
    vi.stubGlobal('indexedDB', { open: () => ({}) } as unknown as IDBFactory)
  }
})

type FakeStore = Map<IDBValidKey, { key: string }>

/** dbName -> storeName -> rows */
const dbs = new Map<string, Map<string, FakeStore>>()
/** Every `put`, so a test can count writes per store. */
const putSpy = vi.fn<(storeName: string, value: unknown) => void>()
/** storeName -> error the next puts should throw. */
const putFailures = new Map<string, unknown>()

vi.mock('idb', () => {
  return {
    openDB: vi.fn(
      async (
        name: string,
        version: number,
        opts?: { upgrade?: (db: unknown, oldVersion: number, newVersion: number) => void },
      ) => {
        if (!dbs.has(name)) dbs.set(name, new Map())
        const stores = dbs.get(name)!

        opts?.upgrade?.(
          {
            objectStoreNames: { contains: (store: string) => stores.has(store) },
            createObjectStore: (store: string) => {
              stores.set(store, new Map())
              return {}
            },
            deleteObjectStore: (store: string) => {
              stores.delete(store)
            },
          },
          1,
          version,
        )

        const storeOf = (store: string): FakeStore => {
          if (!stores.has(store)) stores.set(store, new Map())
          return stores.get(store)!
        }

        return {
          put: async (store: string, value: { key: string }) => {
            putSpy(store, value)
            if (putFailures.has(store)) throw putFailures.get(store)
            storeOf(store).set(value.key, value)
          },
          get: async (store: string, key: IDBValidKey) => storeOf(store).get(key),
          delete: async (store: string, key: IDBValidKey) => {
            storeOf(store).delete(key)
          },
          getAll: async (store: string) => Array.from(storeOf(store).values()),
          getAllKeys: async (store: string) => Array.from(storeOf(store).keys()),
        }
      },
    ),
  }
})

import {
  saveAuditDraft,
  getAuditDraft,
  deleteAuditDraft,
  listAuditDrafts,
  putCaptureBlob,
  listCaptureBlobs,
  deleteCaptureBlob,
  purgeDeviceLedgerForCurrentSession,
  ensureDeviceLedgerDurability,
  subscribeDeviceLedgerStatus,
  getDeviceLedgerStatus,
  resetDeviceLedgerConnection,
  resetDeviceLedgerStatus,
  registerDraftSnapshot,
  flushAllDraftsToIndexedDb,
  DRAFT_TTL_MS,
  type AuditDraft,
} from '../auditDraftStore'

const DB = 'qgp-audit-drafts'

function storeRows(store: string): { key: string }[] {
  return Array.from(dbs.get(DB)?.get(store)?.values() ?? [])
}

function storeKeys(store: string): string[] {
  return Array.from(dbs.get(DB)?.get(store)?.keys() ?? []).map(String)
}

function putCount(store: string): number {
  return putSpy.mock.calls.filter((call) => call[0] === store).length
}

/** A token whose `sub` is what `getCurrentUserId()` will read. */
function signIn(userId: number, tenantId: number): void {
  const payload = btoa(JSON.stringify({ sub: String(userId) }))
  localStorage.setItem('access_token', `header.${payload}.signature`)
  localStorage.setItem('qgp_audit_ledger_identity', `${userId}:${tenantId}`)
}

function signOutLocally(): void {
  localStorage.removeItem('access_token')
  localStorage.removeItem('qgp_audit_ledger_identity')
}

function makeDraft(overrides: Partial<AuditDraft> = {}): AuditDraft {
  return {
    runId: 42,
    responses: {
      q1: { questionId: 'q1', response: 'yes', timestamp: '2026-04-07T00:00:00Z' },
    },
    responseIdMap: { q1: 100 },
    currentSectionIndex: 0,
    currentQuestionIndex: 0,
    savedAt: Date.now(),
    reason: 'autosave',
    ...overrides,
  }
}

function resetLedger(): void {
  // In place, not by replacing the maps: `openDB` closures capture the map they
  // were handed, so swapping it would orphan the reference.
  for (const stores of dbs.values()) {
    for (const rows of stores.values()) rows.clear()
  }
  putFailures.clear()
  putSpy.mockClear()
  resetDeviceLedgerStatus()
}

beforeEach(() => {
  resetLedger()
  localStorage.clear()
  signIn(5, 7)
})

describe('device ledger — namespace', () => {
  it('does not hand one auditor the draft another left on the same tablet', async () => {
    signIn(5, 7)
    await saveAuditDraft(makeDraft({ responses: { q1: mine() } }))

    // Same handset, same run, next shift.
    signIn(9, 7)
    expect(await getAuditDraft(42)).toBeNull()
    expect(await listAuditDrafts()).toEqual([])

    await saveAuditDraft(makeDraft({ responses: { q1: theirs() } }))
    expect((await getAuditDraft(42))?.responses.q1.response).toBe('no')

    signIn(5, 7)
    expect((await getAuditDraft(42))?.responses.q1.response).toBe('yes')

    function mine() {
      return { questionId: 'q1', response: 'yes', timestamp: '2026-04-07T00:00:00Z' }
    }
    function theirs() {
      return { questionId: 'q1', response: 'no', timestamp: '2026-04-07T01:00:00Z' }
    }
  })

  it('separates the same user id in two tenants', async () => {
    signIn(5, 7)
    await saveAuditDraft(makeDraft())
    signIn(5, 8)
    expect(await getAuditDraft(42)).toBeNull()
  })

  it('keys every row by tenant and user, never by run id alone', async () => {
    await saveAuditDraft(makeDraft())
    await putCaptureBlob({
      runId: 42,
      captureId: 'cap-1',
      questionId: 'q1',
      kind: 'photo',
      blob: new Blob(['pixels']),
    })

    expect(storeKeys('ledger')).toEqual(['t7:u5::r42'])
    expect(storeKeys('blobs')).toEqual(['t7:u5::r42::ccap-1'])
  })

  it('writes nothing and says so when the namespace cannot be resolved', async () => {
    signOutLocally()

    const result = await saveAuditDraft(makeDraft())

    expect(result).toEqual({
      ok: false,
      reason: 'no-identity',
      message: expect.stringContaining('not durable on this device'),
    })
    expect(storeRows('ledger')).toEqual([])
    expect(getDeviceLedgerStatus().writeFailed).toBe(true)
  })
})

describe('device ledger — sign-out purge', () => {
  it('purges the signing-out auditor and leaves the other one alone', async () => {
    signIn(9, 7)
    await saveAuditDraft(makeDraft({ runId: 43 }))
    await putCaptureBlob({
      runId: 43,
      captureId: 'theirs',
      questionId: 'q1',
      kind: 'photo',
      blob: new Blob(['theirs']),
    })

    signIn(5, 7)
    await saveAuditDraft(makeDraft())
    await putCaptureBlob({
      runId: 42,
      captureId: 'mine',
      questionId: 'q1',
      kind: 'photo',
      blob: new Blob(['mine']),
    })

    await purgeDeviceLedgerForCurrentSession()

    expect(storeKeys('ledger')).toEqual(['t7:u9::r43'])
    expect(storeKeys('blobs')).toEqual(['t7:u9::r43::ctheirs'])
    // The remembered tenant goes too: the next sign-in must resolve its own.
    expect(localStorage.getItem('qgp_audit_ledger_identity')).toBeNull()
  })

  it('is a no-op rather than a throw when there is no session left to purge', async () => {
    signOutLocally()
    await expect(purgeDeviceLedgerForCurrentSession()).resolves.toBeUndefined()
  })
})

describe('device ledger — blobs are written once, not on every autosave', () => {
  it('never touches the blob store when the answer ledger is saved', async () => {
    await putCaptureBlob({
      runId: 42,
      captureId: 'cap-1',
      questionId: 'q1',
      kind: 'photo',
      blob: new Blob(['pixels']),
    })
    expect(putCount('blobs')).toBe(1)

    // Six autosave ticks over the same run, capture still unsynced.
    for (let tick = 0; tick < 6; tick += 1) {
      await saveAuditDraft(
        makeDraft({
          savedAt: Date.now() + tick,
          responses: {
            q1: {
              questionId: 'q1',
              response: 'captured',
              timestamp: '2026-04-07T00:00:00Z',
              captures: [{ captureId: 'cap-1', kind: 'photo', capturedAt: '2026-04-07T00:00:00Z' }],
            },
          },
        }),
      )
    }

    expect(putCount('ledger')).toBe(6)
    // The kill condition for this slice: "blob store rewritten on every autosave".
    expect(putCount('blobs')).toBe(1)
  })

  it('drops one run\u2019s blobs with its draft and leaves another run\u2019s', async () => {
    await putCaptureBlob({
      runId: 42,
      captureId: 'a',
      questionId: 'q1',
      kind: 'photo',
      blob: new Blob(['a']),
    })
    await putCaptureBlob({
      runId: 43,
      captureId: 'b',
      questionId: 'q1',
      kind: 'photo',
      blob: new Blob(['b']),
    })
    await saveAuditDraft(makeDraft())

    await deleteAuditDraft(42)

    expect(storeKeys('ledger')).toEqual([])
    expect(storeKeys('blobs')).toEqual(['t7:u5::r43::cb'])
  })

  it('reads back only the captures for the run asked for', async () => {
    await putCaptureBlob({
      runId: 42,
      captureId: 'a',
      questionId: 'q1',
      kind: 'photo',
      blob: new Blob(['a']),
    })
    await putCaptureBlob({
      runId: 99,
      captureId: 'b',
      questionId: 'q1',
      kind: 'photo',
      blob: new Blob(['b']),
    })

    const stored = await listCaptureBlobs(42)
    expect(stored.map((capture) => capture.captureId)).toEqual(['a'])

    await deleteCaptureBlob(42, 'a')
    expect(await listCaptureBlobs(42)).toEqual([])
  })
})

describe('device ledger — a failed write is blocking, not a silent false', () => {
  it('reports QuotaExceeded to the auditor instead of swallowing it', async () => {
    const seen: string[] = []
    subscribeDeviceLedgerStatus((next) => {
      if (next.writeFailed) seen.push(next.message)
    })
    const quota = new DOMException('The quota has been exceeded.', 'QuotaExceededError')
    putFailures.set('ledger', quota)

    const result = await saveAuditDraft(makeDraft())

    expect(result.ok).toBe(false)
    expect(result).toMatchObject({ reason: 'quota-exceeded' })
    // "Not saved" has to be the message. The old code returned false and the
    // page said nothing at all, which is how a full tablet passed for a working
    // one until the run was opened somewhere else.
    expect(seen[0]).toContain('NOT saved on this device')
    expect(seen[0]).not.toMatch(/sync/i)
    expect(getDeviceLedgerStatus()).toMatchObject({
      durable: false,
      reason: 'quota-exceeded',
      writeFailed: true,
    })
  })

  it('reports a quota failure on the capture blob too', async () => {
    putFailures.set('blobs', new DOMException('quota', 'QuotaExceededError'))

    const result = await putCaptureBlob({
      runId: 42,
      captureId: 'cap-1',
      questionId: 'q1',
      kind: 'photo',
      blob: new Blob(['pixels']),
    })

    expect(result).toMatchObject({ ok: false, reason: 'quota-exceeded' })
    expect(getDeviceLedgerStatus().writeFailed).toBe(true)
  })

  it('classifies a non-quota put failure as a failed write, still visibly', async () => {
    putFailures.set('ledger', new Error('transaction aborted'))

    const result = await saveAuditDraft(makeDraft())

    expect(result).toMatchObject({ ok: false, reason: 'write-failed' })
    expect(getDeviceLedgerStatus().message).toContain('failed')
  })

  it('clears the failed-write flag once a write lands, without claiming durability', async () => {
    putFailures.set('ledger', new DOMException('quota', 'QuotaExceededError'))
    await saveAuditDraft(makeDraft())
    expect(getDeviceLedgerStatus().writeFailed).toBe(true)

    putFailures.clear()
    await saveAuditDraft(makeDraft())

    expect(getDeviceLedgerStatus().writeFailed).toBe(false)
    // The browser has still not promised anything, so `durable` is not flipped
    // back by a successful put.
    expect(getDeviceLedgerStatus().durable).toBe(false)
  })
})

describe('device ledger — persist() and estimate()', () => {
  function stubStorage(storage: unknown): void {
    Object.defineProperty(navigator, 'storage', {
      value: storage,
      configurable: true,
      writable: true,
    })
  }

  it('asks for durable storage and reports honestly when it is refused', async () => {
    const persist = vi.fn().mockResolvedValue(false)
    stubStorage({
      persisted: vi.fn().mockResolvedValue(false),
      persist,
      estimate: vi.fn().mockResolvedValue({ usage: 1_024, quota: 2_048 }),
    })

    const status = await ensureDeviceLedgerDurability()

    expect(persist).toHaveBeenCalled()
    expect(status).toMatchObject({
      durable: false,
      reason: 'persist-denied',
      usageBytes: 1_024,
      quotaBytes: 2_048,
    })
    expect(status.message).toContain('not durable on this device')
    // Nothing here retries a server write, so nothing may imply one.
    expect(status.message).not.toMatch(/sync/i)
  })

  it('does not ask again when the browser has already granted persistence', async () => {
    const persist = vi.fn()
    stubStorage({
      persisted: vi.fn().mockResolvedValue(true),
      persist,
      estimate: vi.fn().mockResolvedValue({ usage: 10, quota: 20 }),
    })

    const status = await ensureDeviceLedgerDurability()

    expect(persist).not.toHaveBeenCalled()
    expect(status).toMatchObject({ durable: true, reason: 'ok', usageBytes: 10, quotaBytes: 20 })
    expect(status.message).toBe('')
  })

  it('treats a browser with no Storage API as not durable rather than assuming', async () => {
    stubStorage(undefined)

    const status = await ensureDeviceLedgerDurability()

    expect(status).toMatchObject({ durable: false, reason: 'persist-unsupported' })
    expect(status.message).toContain('not durable on this device')
  })

  it('says the audit is not durable here when the namespace is unknown', async () => {
    signOutLocally()
    stubStorage({ persisted: vi.fn().mockResolvedValue(true) })

    const status = await ensureDeviceLedgerDurability()

    expect(status).toMatchObject({ durable: false, reason: 'no-identity' })
  })
})

describe('device ledger — what must never reach the device', () => {
  it('stores no entity pick-list label and no preview URL', async () => {
    await saveAuditDraft(
      makeDraft({
        responses: {
          q1: {
            questionId: 'q1',
            // The answer is the entity id, which is kept.
            response: '4821',
            // The label is a staff member's name. It is not.
            entityLabel: 'Jamie Okonkwo',
            timestamp: '2026-04-07T00:00:00Z',
            captures: [
              {
                captureId: 'cap-1',
                kind: 'photo',
                capturedAt: '2026-04-07T00:00:00Z',
                evidenceAssetId: 501,
                // A signed URL expires; an object URL dies with the document.
                previewUrl: 'https://blob.core.windows.net/x.jpg?sig=REDACTED',
              },
            ],
          },
        },
      } as unknown as Partial<AuditDraft>),
    )

    const serialised = JSON.stringify(storeRows('ledger'))
    expect(serialised).not.toContain('Jamie Okonkwo')
    expect(serialised).not.toContain('entityLabel')
    expect(serialised).not.toContain('previewUrl')
    expect(serialised).not.toContain('sig=')

    const restored = await getAuditDraft(42)
    expect(restored?.responses.q1.response).toBe('4821')
    expect(restored?.responses.q1.captures).toEqual([
      {
        captureId: 'cap-1',
        kind: 'photo',
        capturedAt: '2026-04-07T00:00:00Z',
        evidenceAssetId: 501,
      },
    ])
  })

  it('leaves the v1 run-keyed store unreadable rather than migrating it', async () => {
    // A v1 database, holding a record whose owner was never recorded.
    resetDeviceLedgerConnection()
    dbs.delete(DB)
    dbs.set(
      DB,
      new Map([
        ['drafts', new Map([[42, { key: 'legacy', runId: 42 } as { key: string }]])] as [
          string,
          FakeStore,
        ],
      ]),
    )

    await saveAuditDraft(makeDraft())

    expect(dbs.get(DB)?.has('drafts')).toBe(false)
    expect(storeKeys('ledger')).toEqual(['t7:u5::r42'])
  })
})

describe('device ledger — TTL', () => {
  it('refuses to offer a fortnight-old draft, and drops it on the read', async () => {
    await saveAuditDraft(makeDraft({ savedAt: Date.now() - DRAFT_TTL_MS - 1 }))

    expect(await getAuditDraft(42)).toBeNull()
    expect(storeKeys('ledger')).toEqual([])
  })

  it('still offers a draft inside the window', async () => {
    await saveAuditDraft(makeDraft({ savedAt: Date.now() - DRAFT_TTL_MS + 60_000 }))
    expect(await getAuditDraft(42)).not.toBeNull()
  })
})

describe('device ledger — auth-loss flush', () => {
  it('resolves the namespace before the token is cleared out from under it', async () => {
    const unregister = registerDraftSnapshot(7, () => makeDraft({ runId: 7 }))

    // Exactly what `clearAndRedirectToLogin` does: kick the flush off, then wipe
    // auth state synchronously in the same tick. If the namespace were resolved
    // inside the async write, this draft would be attributed to nobody.
    const flushed = flushAllDraftsToIndexedDb('auth-loss')
    signOutLocally()
    await flushed

    expect(storeKeys('ledger')).toEqual(['t7:u5::r7'])
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

  it('reports rather than drops a flush it cannot attribute', async () => {
    signOutLocally()
    const unregister = registerDraftSnapshot(13, () => makeDraft({ runId: 13 }))

    await flushAllDraftsToIndexedDb('auth-loss')

    expect(storeRows('ledger')).toEqual([])
    expect(getDeviceLedgerStatus()).toMatchObject({ reason: 'no-identity', writeFailed: true })
    unregister()
  })
})

describe('device ledger — CRUD basics', () => {
  it('saves and retrieves a draft for the signed-in auditor', async () => {
    const draft = makeDraft()
    expect(await saveAuditDraft(draft)).toEqual({ ok: true })
    expect(await getAuditDraft(42)).toEqual(draft)
  })

  it('returns null when no draft exists for the run', async () => {
    expect(await getAuditDraft(999)).toBeNull()
  })

  it('overwrites an existing draft for the same run', async () => {
    await saveAuditDraft(makeDraft({ savedAt: Date.now() - 2, reason: 'autosave' }))
    await saveAuditDraft(makeDraft({ savedAt: Date.now() - 1, reason: 'auth-loss' }))
    expect((await getAuditDraft(42))?.reason).toBe('auth-loss')
    expect(storeKeys('ledger')).toHaveLength(1)
  })

  it('deletes a draft', async () => {
    await saveAuditDraft(makeDraft())
    await deleteAuditDraft(42)
    expect(await getAuditDraft(42)).toBeNull()
  })

  it('lists only the signed-in auditor\u2019s drafts', async () => {
    await saveAuditDraft(makeDraft({ runId: 1 }))
    await saveAuditDraft(makeDraft({ runId: 2 }))
    signIn(9, 7)
    await saveAuditDraft(makeDraft({ runId: 3 }))

    expect((await listAuditDrafts()).map((draft) => draft.runId)).toEqual([3])
    signIn(5, 7)
    expect((await listAuditDrafts()).map((draft) => draft.runId).sort()).toEqual([1, 2])
  })
})
