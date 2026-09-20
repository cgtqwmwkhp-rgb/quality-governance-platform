import { describe, expect, it } from 'vitest'
import {
  buildActivitySpine,
  filterActivitySpine,
  filterActivitySpineByOrigin,
  originOf,
} from '../activitySpine'
import type { Action, CustomerPackSummary, EvidenceAsset, InvestigationComment, TimelineEvent } from '../../../api/client'

describe('activitySpine', () => {
  it('merges comments, CAPA, evidence, packs, and revision events newest-first', () => {
    const spine = buildActivitySpine({
      timeline: [
        {
          id: 1,
          event_type: 'CREATED',
          created_at: '2026-07-01T10:00:00Z',
        } as TimelineEvent,
        {
          id: 2,
          event_type: 'MANUAL_ENTRY',
          created_at: '2026-07-02T10:00:00Z',
          new_value: 'Site visit',
        } as TimelineEvent,
      ],
      comments: [
        {
          id: 9,
          investigation_id: 1,
          content: 'Note',
          author_id: 3,
          created_at: '2026-07-03T10:00:00Z',
        } as InvestigationComment,
      ],
      actions: [
        {
          id: 4,
          title: 'Fix guard',
          description: 'd',
          action_type: 'corrective',
          priority: 'high',
          status: 'open',
          display_status: 'open',
          action_key: 'capa:4',
          source_type: 'investigation',
          source_id: 1,
          created_at: '2026-07-04T10:00:00Z',
          reference_number: 'CAPA-1',
        } as Action,
      ],
      evidence: [
        {
          id: 5,
          title: 'Photo',
          visibility: 'internal_customer',
          created_at: '2026-07-05T10:00:00Z',
          contains_pii: false,
        } as EvidenceAsset,
      ],
      packs: [
        {
          id: 6,
          generated_at: '2026-07-06T10:00:00Z',
          pack_uuid: 'abc',
          audience: 'external_customer',
        } as CustomerPackSummary,
      ],
    })

    expect(spine[0].kind).toBe('pack')
    expect(spine.map((i) => i.kind)).toEqual([
      'pack',
      'evidence',
      'capa',
      'comment',
      'manual',
      'revision',
    ])
    expect(filterActivitySpine(spine, 'CAPA')).toHaveLength(1)
    expect(filterActivitySpine(spine, 'MANUAL_ENTRY')[0].body).toBe('Site visit')
    expect(spine.every((i) => i.origin === 'investigation')).toBe(true)
  })
})

describe('activitySpine parent-source rows (INV-C9)', () => {
  const sourceAudit = {
    id: -91,
    event_type: 'SOURCE_AUDIT',
    created_at: '2026-07-02T10:00:00Z',
    new_value: 'Incident INC-2026-0001 closed',
    event_metadata: {
      origin: 'source',
      source_feed: 'audit',
      source_label: 'Incident · update',
      source_row_id: 9,
    },
  } as TimelineEvent

  const sourceNote = {
    id: -82,
    event_type: 'SOURCE_RUNNING_SHEET',
    created_at: '2026-06-30T10:00:00Z',
    new_value: 'Attended site, spoke to the operator',
    event_metadata: {
      origin: 'source',
      source_feed: 'running_sheet',
      source_label: 'Incident · running sheet',
      source_row_id: 8,
    },
  } as TimelineEvent

  const investigationEvent = {
    id: 1,
    event_type: 'STATUS_CHANGED',
    created_at: '2026-07-01T10:00:00Z',
  } as TimelineEvent

  const build = (timeline: TimelineEvent[]) =>
    buildActivitySpine({ timeline, comments: [], actions: [], evidence: [], packs: [] })

  it('reads origin from event_metadata and defaults anything else to the investigation', () => {
    expect(originOf(sourceAudit)).toBe('source')
    expect(originOf(investigationEvent)).toBe('investigation')
    expect(originOf({ ...investigationEvent, event_metadata: { origin: 'elsewhere' } } as TimelineEvent)).toBe(
      'investigation',
    )
  })

  it('interleaves source rows into the chronology by date, not after it', () => {
    const spine = build([investigationEvent, sourceAudit, sourceNote])

    expect(spine.map((i) => i.id)).toEqual(['src-91', 'rev-1', 'src-82'])
    expect(spine.map((i) => i.kind)).toEqual(['source', 'revision', 'source'])
  })

  it('keys a source row apart from a revision event that shares its row number', () => {
    const spine = build([{ ...investigationEvent, id: 91 } as TimelineEvent, sourceAudit])

    expect(new Set(spine.map((i) => i.id)).size).toBe(2)
    expect(spine.map((i) => i.id)).toContain('rev-91')
    expect(spine.map((i) => i.id)).toContain('src-91')
  })

  it('titles a source row from its label rather than the coarse event_type', () => {
    const [audit, note] = build([sourceAudit, sourceNote])

    expect(audit.title).toBe('Incident · update')
    expect(audit.body).toBe('Incident INC-2026-0001 closed')
    expect(note.title).toBe('Incident · running sheet')
  })

  it('offers no in-page jump for a row the page does not own', () => {
    expect(build([sourceAudit])[0].hrefTab).toBeUndefined()
  })

  it('does not mistake a source row for a manual investigation entry', () => {
    const spine = build([
      { ...sourceAudit, event_type: 'MANUAL_ENTRY' } as TimelineEvent,
    ])

    expect(spine[0].kind).toBe('source')
    expect(spine[0].hrefTab).toBeUndefined()
  })

  it('filters to one origin and treats an unknown value as no filter', () => {
    const spine = build([investigationEvent, sourceAudit, sourceNote])

    expect(filterActivitySpineByOrigin(spine, 'source').map((i) => i.id)).toEqual(['src-91', 'src-82'])
    expect(filterActivitySpineByOrigin(spine, 'investigation').map((i) => i.id)).toEqual(['rev-1'])
    expect(filterActivitySpineByOrigin(spine, 'all')).toHaveLength(3)
    expect(filterActivitySpineByOrigin(spine, '')).toHaveLength(3)
  })

  it('composes with the event_type filter rather than replacing it', () => {
    const spine = build([investigationEvent, sourceAudit, sourceNote])

    expect(
      filterActivitySpineByOrigin(filterActivitySpine(spine, 'SOURCE_AUDIT'), 'source').map((i) => i.id),
    ).toEqual(['src-91'])
  })
})
