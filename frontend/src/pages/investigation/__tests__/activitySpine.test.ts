import { describe, expect, it } from 'vitest'
import { buildActivitySpine, filterActivitySpine } from '../activitySpine'
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
  })
})
