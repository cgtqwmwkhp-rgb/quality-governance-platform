import { describe, expect, it } from 'vitest'
import type { CustomerPackSummary } from '../../../api/investigationsClient'
import {
  BLOCKER_NOT_COMPLETE,
  BLOCKER_REDACTION_REVIEW_NOT_CLEARED,
  externalIssueBlockers,
  issueBlockedSentence,
  packIssueSummary,
} from '../packIssueCopy'

function pack(overrides: Partial<CustomerPackSummary> = {}): CustomerPackSummary {
  return {
    id: 1,
    generated_at: '2026-09-08T10:00:00Z',
    pack_uuid: 'pack-uuid-1',
    audience: 'external_customer',
    ...overrides,
  }
}

describe('packIssueCopy', () => {
  it('does not gate an internal pack', () => {
    expect(
      externalIssueBlockers(pack({ audience: 'internal_customer' }), 'in_progress'),
    ).toEqual([])
  })

  it('names both blockers on an incomplete unreviewed external pack', () => {
    const blockers = externalIssueBlockers(pack(), 'in_progress')
    expect(blockers).toEqual([BLOCKER_NOT_COMPLETE, BLOCKER_REDACTION_REVIEW_NOT_CLEARED])
    expect(issueBlockedSentence(blockers)).toBe(
      'This pack cannot be issued to a customer because the investigation is not complete and the redaction review has not been cleared.',
    )
  })

  it('treats closed as complete', () => {
    expect(
      externalIssueBlockers(
        pack({ redaction_review_cleared_at: '2026-09-08T11:00:00Z' }),
        'closed',
      ),
    ).toEqual([])
  })

  it('says generating is not issuing until a review is cleared', () => {
    expect(packIssueSummary(pack())).toContain('Generating a pack is not the same as issuing it')
  })

  it('says download returns the retained copy once issued', () => {
    expect(
      packIssueSummary(
        pack({
          issued_at: '2026-09-08T12:00:00Z',
          issued_pdf_sha256: 'abc',
          disclosure_count: 1,
        }),
      ),
    ).toBe('Issued once. Download returns the retained copy, not a live re-render.')
  })
})
