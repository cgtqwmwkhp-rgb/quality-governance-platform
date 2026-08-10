import { describe, expect, it, vi } from 'vitest'
import type { AxiosInstance } from 'axios'

import {
  createApprovalsApi,
  decisionsAreComplete,
  describeUnavailableDecisionSources,
  unattributedDecisionCount,
  unavailableSourceReasons,
} from './approvalsClient'

describe('approvals client', () => {
  it('reads the one endpoint it has, and offers no way to decide anything', () => {
    const api = { get: vi.fn(), post: vi.fn() } as unknown as AxiosInstance
    const approvals = createApprovalsApi(api)

    approvals.myDecisions()

    expect(api.get).toHaveBeenCalledWith('/api/v1/approvals/my-decisions')
    // Recording a decision belongs to the domain that raised it, so that the
    // audit trail sits next to the record. A write method here would be a second
    // place for approvals to live.
    expect(Object.keys(approvals)).toEqual(['myDecisions'])
  })
})

describe('decisionsAreComplete', () => {
  it('is true only when the server says every source answered', () => {
    expect(decisionsAreComplete({ sources_complete: true })).toBe(true)
    expect(decisionsAreComplete({ sources_complete: false })).toBe(false)
  })

  it('treats a missing flag as incomplete', () => {
    // The opposite default to actionsAreComplete, deliberately: this panel's
    // whole claim is "these are all your decisions", and a response we cannot
    // interpret is not evidence for it.
    expect(decisionsAreComplete({})).toBe(false)
  })
})

describe('describeUnavailableDecisionSources', () => {
  it('names unreadable sources with the label the server sent', () => {
    const described = describeUnavailableDecisionSources({
      unavailable_sources: ['document_approval'],
      sources: [
        {
          key: 'document_approval',
          label: 'Controlled documents naming me as approver',
          status: 'unavailable',
        },
        {
          key: 'signature_request',
          label: 'Signature requests awaiting my signature',
          status: 'live',
          count: 0,
        },
      ],
    })

    expect(described).toBe('Controlled documents naming me as approver')
  })

  it('falls back to the key when a source is not described', () => {
    expect(
      describeUnavailableDecisionSources({
        unavailable_sources: ['brand_new_source'],
        sources: [],
      }),
    ).toBe('brand_new_source')
  })

  it('is empty when everything answered', () => {
    expect(describeUnavailableDecisionSources({ unavailable_sources: [], sources: [] })).toBe('')
    expect(describeUnavailableDecisionSources({})).toBe('')
  })
})

describe('unavailableSourceReasons', () => {
  it('returns the reasons only for sources that could not be read', () => {
    const reasons = unavailableSourceReasons({
      unavailable_sources: ['document_approval'],
      sources: [
        {
          key: 'document_approval',
          label: 'Documents',
          status: 'unavailable',
          reason: 'document_approval_instances is absent from this database.',
        },
        { key: 'signature_request', label: 'Signatures', status: 'live', count: 2, reason: null },
      ],
    })

    expect(reasons).toEqual(['document_approval_instances is absent from this database.'])
  })
})

describe('unattributedDecisionCount', () => {
  it('adds up approvals that name nobody, across sources', () => {
    expect(
      unattributedDecisionCount({
        sources: [
          {
            key: 'document_approval',
            label: 'Documents',
            status: 'live',
            count: 1,
            unattributed: 2,
          },
          { key: 'signature_request', label: 'Signatures', status: 'live', count: 0 },
        ],
      }),
    ).toBe(2)
  })

  it('is zero when no source reports any', () => {
    expect(unattributedDecisionCount({ sources: [] })).toBe(0)
    expect(unattributedDecisionCount({})).toBe(0)
  })
})
