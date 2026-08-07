import { describe, expect, it } from 'vitest'
import {
  confidenceChipClass,
  isFraOcrEligible,
  proposeNextDueDate,
} from '../fraOcrHelpers'
import type { FraOcrDraftResponse } from '../../../api/complianceScheduleFraOcrClient'
import type { ComplianceRequirement } from '../../../api/complianceScheduleClient'

function requirement(
  overrides: Partial<ComplianceRequirement> = {},
): Pick<ComplianceRequirement, 'is_active' | 'location_id' | 'taxonomy_id'> {
  return {
    is_active: true,
    location_id: 12,
    taxonomy_id: '03.01',
    ...overrides,
  }
}

function emptyField(value: string | null = null) {
  return { value, confidence: 'none' as const, evidence_snippet: null }
}

function draft(overrides: Partial<FraOcrDraftResponse> = {}): FraOcrDraftResponse {
  return {
    id: 1,
    external_id: 'ext-1',
    tenant_id: 1,
    requirement_id: 7,
    purpose: 'fra_pas79',
    status: 'pending',
    source_checksum_sha256: 'abc',
    proposed: {
      assessment_date: emptyField(),
      next_review_date: emptyField('2027-03-01'),
      review_interval_months: emptyField(),
      assessor_name: emptyField(),
      assessor_organisation: emptyField(),
      premises_name: emptyField(),
      pas79_reference: emptyField(),
      overall_risk_rating: emptyField(),
    },
    proposed_actions: [],
    warnings: [],
    filing_status: 'not_filed',
    created_at: '2026-08-01T10:00:00Z',
    ...overrides,
  }
}

describe('isFraOcrEligible', () => {
  it('requires active, site-scoped, taxonomy 03.01', () => {
    expect(isFraOcrEligible(requirement())).toBe(true)
  })

  it('rejects inactive obligations', () => {
    expect(isFraOcrEligible(requirement({ is_active: false }))).toBe(false)
  })

  it('rejects org-wide (no location) obligations', () => {
    expect(isFraOcrEligible(requirement({ location_id: null }))).toBe(false)
  })

  it('rejects non-FRA taxonomy', () => {
    expect(isFraOcrEligible(requirement({ taxonomy_id: '03.02' }))).toBe(false)
  })
})

describe('proposeNextDueDate', () => {
  it('returns ISO next_review_date when present', () => {
    expect(proposeNextDueDate(draft())).toBe('2027-03-01')
  })

  it('returns empty string when value is not ISO-looking', () => {
    expect(
      proposeNextDueDate(
        draft({
          proposed: {
            ...draft().proposed,
            next_review_date: emptyField('March 2027'),
          },
        }),
      ),
    ).toBe('')
  })

  it('returns empty string when proposal is missing', () => {
    expect(
      proposeNextDueDate(
        draft({
          proposed: {
            ...draft().proposed,
            next_review_date: emptyField(null),
          },
        }),
      ),
    ).toBe('')
  })
})

describe('confidenceChipClass', () => {
  it('maps high / medium / none to distinct chip classes', () => {
    expect(confidenceChipClass('high')).toContain('emerald')
    expect(confidenceChipClass('medium')).toContain('amber')
    expect(confidenceChipClass('none')).toContain('muted')
    expect(confidenceChipClass(undefined)).toContain('muted')
  })
})
