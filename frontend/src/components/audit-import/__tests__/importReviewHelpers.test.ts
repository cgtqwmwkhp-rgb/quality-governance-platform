import { describe, expect, it } from 'vitest'
import {
  deriveDeclaredProgramLabel,
  deriveSpecialistHome,
  humanizeLabel,
} from '../importReviewHelpers'

describe('importReviewHelpers (Audit Import Review phase 2)', () => {
  it('humanizeLabel replaces underscores', () => {
    expect(humanizeLabel('customer_other')).toBe('customer other')
    expect(humanizeLabel(null)).toBe('')
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

  it('deriveSpecialistHome falls back to customer audits', () => {
    expect(deriveSpecialistHome(null)).toEqual({
      path: '/customer-audits',
      label: 'Open Customer Audits',
    })
  })
})
