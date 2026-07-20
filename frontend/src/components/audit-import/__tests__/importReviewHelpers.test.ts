import { describe, expect, it } from 'vitest'
import {
  deriveDeclaredProgramLabel,
  deriveSpecialistHome,
  getImportReviewPath,
  humanizeLabel,
} from '../importReviewHelpers'

describe('importReviewHelpers (Audit Import Review phase 2)', () => {
  it('humanizeLabel replaces underscores', () => {
    expect(humanizeLabel('customer_other')).toBe('customer other')
    expect(humanizeLabel(null)).toBe('')
  })

  it('getImportReviewPath requires a real audit run id', () => {
    expect(getImportReviewPath(0, 72)).toBeNull()
    expect(getImportReviewPath(null, 72)).toBeNull()
    expect(getImportReviewPath(41, 72)).toBe('/audits/41/import-review?jobId=72')
    expect(getImportReviewPath(41)).toBe('/audits/41/import-review')
  })

  it('deriveDeclaredProgramLabel prefers Achilles / UVDB schemes', () => {
    expect(
      deriveDeclaredProgramLabel(null, {
        id: 1,
        status: 'pending_review',
        provenance_json: { declared_assurance_scheme: 'Achilles UVDB' },
      } as never),
    ).toBe('Achilles / UVDB')
  })

  it('deriveSpecialistHome falls back to customer audits programme home', () => {
    expect(deriveSpecialistHome(null)).toEqual({
      path: '/customer-audits',
      label: 'Open Customer Audits',
    })
  })
})
