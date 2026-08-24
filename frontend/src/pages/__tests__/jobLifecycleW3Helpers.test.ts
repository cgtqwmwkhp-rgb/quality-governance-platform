/**
 * JL-UX-W3 helpers — freshness toggle persistence, chip vocabulary, obsolete
 * pre-flight, audit-lapse copy.
 *
 * The recurring assertion is that absence never reads as reassurance: a
 * document with no verdict is "Unknown", not "Current", and an audit link with
 * no cadence is "Unknown", not "In date".
 */
import { describe, expect, it } from 'vitest'
import type { JobCell, JobDocumentFreshness } from '../../api/jobLifecycleClient'
import {
  DEFAULT_JOB_LIFECYCLE_FRESHNESS,
  FRESHNESS_ID_REQUEST_LIMIT,
  JOB_LIFECYCLE_FRESHNESS_STORAGE_KEY,
  auditLapseClasses,
  auditLapseLabel,
  auditLapseTitle,
  buildFreshnessIndex,
  collectFreshnessDocumentIds,
  freshnessStateClasses,
  freshnessStateLabel,
  freshnessTitle,
  isObsoleteLibraryStatus,
  mergeFreshnessIndex,
  missingFreshnessIds,
  obsoleteAttachBlock,
  parseStoredJobLifecycleFreshness,
  readStoredJobLifecycleFreshness,
  resolveJobLifecycleFreshness,
  writeStoredJobLifecycleFreshness,
} from '../jobLifecycleHelpers'

const NOW = '2026-08-08T00:00:00Z'

function verdict(overrides: Partial<JobDocumentFreshness> = {}): JobDocumentFreshness {
  return {
    library_document_id: 1,
    found: true,
    title: 'Lifting plan',
    reference: 'PEL-1',
    library_status: 'approved',
    controlled_status: null,
    state: 'current',
    reason: 'review_current',
    review_date: NOW,
    is_obsolete: false,
    ...overrides,
  }
}

function cell(id: number, laneId: number, docIds: number[]): JobCell {
  return {
    id,
    tenant_id: 1,
    job_type_id: 1,
    lane_id: laneId,
    step_id: 20,
    library_document_ids: docIds,
    created_at: NOW,
    updated_at: NOW,
  }
}

describe('freshness toggle persistence', () => {
  it('defaults to off so the composer opens calm', () => {
    expect(DEFAULT_JOB_LIFECYCLE_FRESHNESS).toBe(false)
    expect(resolveJobLifecycleFreshness(null)).toBe(false)
    expect(resolveJobLifecycleFreshness(undefined)).toBe(false)
  })

  it('round-trips through storage', () => {
    const store = new Map<string, string>()
    const storage = {
      getItem: (k: string) => store.get(k) ?? null,
      setItem: (k: string, v: string) => void store.set(k, v),
    }
    writeStoredJobLifecycleFreshness(true, storage)
    expect(store.get(JOB_LIFECYCLE_FRESHNESS_STORAGE_KEY)).toBe('on')
    expect(readStoredJobLifecycleFreshness(storage)).toBe(true)

    writeStoredJobLifecycleFreshness(false, storage)
    expect(readStoredJobLifecycleFreshness(storage)).toBe(false)
  })

  it('treats an unrecognised stored value as no preference, not as on', () => {
    expect(parseStoredJobLifecycleFreshness('yes')).toBeNull()
    expect(parseStoredJobLifecycleFreshness(null)).toBeNull()
    expect(resolveJobLifecycleFreshness(parseStoredJobLifecycleFreshness('yes'))).toBe(false)
  })

  it('survives storage that throws', () => {
    const hostile = {
      getItem: () => {
        throw new Error('denied')
      },
      setItem: () => {
        throw new Error('denied')
      },
    }
    expect(readStoredJobLifecycleFreshness(hostile)).toBeNull()
    expect(() => writeStoredJobLifecycleFreshness(true, hostile)).not.toThrow()
    expect(readStoredJobLifecycleFreshness(null)).toBeNull()
  })
})

describe('freshness chip vocabulary', () => {
  it('labels every state, and an absent state as Unknown', () => {
    expect(freshnessStateLabel('current')).toBe('Current')
    expect(freshnessStateLabel('due_soon')).toBe('Review due')
    expect(freshnessStateLabel('overdue')).toBe('Overdue')
    expect(freshnessStateLabel('obsolete')).toBe('Obsolete')
    expect(freshnessStateLabel('unknown')).toBe('Unknown')
  })

  it('does not style unknown like current', () => {
    expect(freshnessStateClasses('unknown')).not.toEqual(freshnessStateClasses('current'))
    expect(freshnessStateClasses('obsolete')).toEqual(freshnessStateClasses('overdue'))
  })

  it('explains an unknown honestly instead of implying the document is fine', () => {
    expect(freshnessTitle(undefined)).toMatch(/unknown/i)
    expect(freshnessTitle(verdict({ state: 'unknown', reason: 'no_review_date' }))).toMatch(
      /no review date recorded/i,
    )
    expect(
      freshnessTitle(verdict({ state: 'unknown', reason: 'document_not_found', found: false })),
    ).toMatch(/not visible in your library/i)
  })

  it('names which record withdrew the document', () => {
    expect(
      freshnessTitle(
        verdict({ state: 'obsolete', reason: 'obsolete_controlled_status', controlled_status: 'obsolete' }),
      ),
    ).toMatch(/Document Control/)
    expect(
      freshnessTitle(
        verdict({ state: 'obsolete', reason: 'obsolete_library_status', library_status: 'superseded' }),
      ),
    ).toMatch(/Library/)
  })
})

describe('freshness index', () => {
  it('builds and merges without losing previously known ids', () => {
    const first = buildFreshnessIndex([verdict({ library_document_id: 1 })])
    const merged = mergeFreshnessIndex(first, [
      verdict({ library_document_id: 2, state: 'overdue' }),
    ])
    expect(merged.get(1)?.state).toBe('current')
    expect(merged.get(2)?.state).toBe('overdue')
    expect(first.has(2)).toBe(false)
  })

  it('lets a later verdict replace an earlier one for the same id', () => {
    const merged = mergeFreshnessIndex(buildFreshnessIndex([verdict()]), [
      verdict({ state: 'obsolete', is_obsolete: true }),
    ])
    expect(merged.get(1)?.state).toBe('obsolete')
  })

  it('reports only the ids nothing is known about', () => {
    const known = buildFreshnessIndex([verdict({ library_document_id: 1 })])
    expect(missingFreshnessIds(known, [1, 2, 3])).toEqual([2, 3])
    expect(missingFreshnessIds(new Set([2]), [1, 2])).toEqual([1])
  })
})

describe('collectFreshnessDocumentIds', () => {
  it('covers cell refs and tray docs, deduped', () => {
    const ids = collectFreshnessDocumentIds({
      libraryDocs: [
        { id: 3, title: 'C' },
        { id: 1, title: 'A' },
      ],
      cells: [cell(100, 10, [1, 2]), cell(101, 11, [2])],
    })
    expect(ids).toEqual([1, 2, 3])
  })

  it('keeps cell refs when the cap bites — those drive attach decisions', () => {
    const ids = collectFreshnessDocumentIds({
      libraryDocs: [
        { id: 90, title: 'tray' },
        { id: 91, title: 'tray' },
      ],
      cells: [cell(100, 10, [7])],
      limit: 2,
    })
    expect(ids).toEqual([7, 90])
  })

  it('defaults to the same cap the service enforces', () => {
    const ids = collectFreshnessDocumentIds({
      libraryDocs: Array.from({ length: 400 }, (_, i) => ({ id: i + 1, title: 'x' })),
      cells: [],
    })
    expect(ids).toHaveLength(FRESHNESS_ID_REQUEST_LIMIT)
  })

  it('ignores ids that are not usable', () => {
    const ids = collectFreshnessDocumentIds({
      libraryDocs: [{ id: 0, title: 'zero' }, { id: 5, title: 'ok' }],
      cells: [{ ...cell(100, 10, []), library_document_ids: [-1, Number.NaN] as number[] }],
    })
    expect(ids).toEqual([5])
  })
})

describe('obsolete attach pre-flight', () => {
  it('blocks a document the freshness lookup calls obsolete', () => {
    const index = buildFreshnessIndex([
      verdict({ state: 'obsolete', reason: 'obsolete_library_status', is_obsolete: true }),
    ])
    const result = obsoleteAttachBlock({ documentId: 1, freshness: index })
    expect(result.blocked).toBe(true)
    expect(result.reason).toMatch(/Obsolete documents cannot be attached/)
  })

  it('blocks on the raw tray status before any lookup has answered', () => {
    const result = obsoleteAttachBlock({
      documentId: 1,
      freshness: new Map(),
      libraryStatus: 'Superseded',
    })
    expect(result.blocked).toBe(true)
    expect(result.reason).toMatch(/Superseded/)
  })

  it('allows an unknown document rather than blocking on no evidence', () => {
    const index = buildFreshnessIndex([verdict({ state: 'unknown', reason: 'no_review_date' })])
    expect(obsoleteAttachBlock({ documentId: 1, freshness: index }).blocked).toBe(false)
    expect(obsoleteAttachBlock({ documentId: 99, freshness: index }).blocked).toBe(false)
  })

  it('lets a server verdict override a stale tray status', () => {
    const index = buildFreshnessIndex([verdict({ state: 'current' })])
    expect(
      obsoleteAttachBlock({ documentId: 1, freshness: index, libraryStatus: 'obsolete' }).blocked,
    ).toBe(false)
  })

  it('recognises the withdrawn library statuses and nothing else', () => {
    for (const status of ['obsolete', 'Superseded', 'RETIRED', 'archived']) {
      expect(isObsoleteLibraryStatus(status)).toBe(true)
    }
    for (const status of ['approved', 'published', 'draft', '', null, undefined]) {
      expect(isObsoleteLibraryStatus(status)).toBe(false)
    }
  })
})

describe('audit lapse cues', () => {
  it('labels each state and never calls unknown "in date"', () => {
    expect(auditLapseLabel('current')).toBe('In date')
    expect(auditLapseLabel('due_soon')).toBe('Audit due')
    expect(auditLapseLabel('lapsed')).toBe('Lapsed')
    expect(auditLapseLabel('unknown')).toBe('Unknown')
    expect(auditLapseClasses('unknown')).not.toEqual(auditLapseClasses('current'))
  })

  it('explains why a cadence is unknown', () => {
    expect(auditLapseTitle(null)).toMatch(/unknown/i)
    expect(auditLapseTitle({ state: 'unknown', reason: 'no_audit_cadence' })).toMatch(/ad-hoc/i)
    expect(auditLapseTitle({ state: 'unknown', reason: 'audit_not_completed' })).toMatch(
      /not completed/i,
    )
    expect(auditLapseTitle({ state: 'unknown', reason: 'no_audit_run' })).toMatch(/not readable/i)
  })

  it('quotes the due date it is judging against', () => {
    const title = auditLapseTitle({
      state: 'lapsed',
      reason: 'cadence_overdue',
      next_due_at: NOW,
    })
    expect(title).toMatch(/Repeat audit was due/)
    expect(title).toContain(new Date(NOW).toLocaleDateString())
  })
})
