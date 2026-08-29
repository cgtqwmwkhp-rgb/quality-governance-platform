import { describe, expect, it } from 'vitest'
import {
  isAuditorConfirmedConformance,
  isProposedLink,
  isRejectedLink,
  sourceIdentityLabel,
} from '../complianceEvidenceHonesty'

describe('complianceEvidenceHonesty', () => {
  it('counts confirmed evidence and legacy manual rows', () => {
    expect(
      isAuditorConfirmedConformance({
        status: 'confirmed',
        signal_type: 'evidence',
        linked_by: 'ai',
        confirmed_at: '2026-08-28T22:56:47Z',
      }),
    ).toBe(true)
    expect(isAuditorConfirmedConformance({ linked_by: 'manual' })).toBe(true)
  })

  it('does not count AI proposals, NC signals, or rejected rows as coverage', () => {
    expect(
      isAuditorConfirmedConformance({
        status: 'proposed',
        signal_type: 'nonconformity',
        linked_by: 'ai',
        confirmed_at: null,
      }),
    ).toBe(false)
    expect(
      isAuditorConfirmedConformance({
        status: 'rejected',
        signal_type: 'evidence',
        linked_by: 'ai',
      }),
    ).toBe(false)
    expect(
      isAuditorConfirmedConformance({
        status: 'confirmed',
        signal_type: 'nonconformity',
        linked_by: 'manual',
      }),
    ).toBe(false)
  })

  it('classifies proposed vs rejected', () => {
    expect(isProposedLink({ status: 'proposed', linked_by: 'ai' })).toBe(true)
    expect(isProposedLink({ linked_by: 'ai', confirmed_at: null })).toBe(true)
    expect(isRejectedLink({ status: 'Rejected' })).toBe(true)
    expect(isProposedLink({ status: 'confirmed', linked_by: 'ai' })).toBe(false)
  })

  it('names the source entity without inventing a register title', () => {
    expect(sourceIdentityLabel({ entity_type: 'incident', entity_id: '138' })).toBe(
      'incident 138',
    )
  })
})
