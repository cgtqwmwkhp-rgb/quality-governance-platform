import { describe, expect, it } from 'vitest'
import { renderHook } from '@testing-library/react'
import { useImportReviewDerived } from '../useImportReviewDerived'
import type { ExternalAuditImportDraft } from '../../../api/client'

const draft = (overrides: Partial<ExternalAuditImportDraft>): ExternalAuditImportDraft =>
  ({
    id: 1,
    status: 'draft',
    finding_type: 'non_conformity',
    severity: 'high',
    promoted_finding_id: null,
    mapped_standards_json: [],
    ...overrides,
  }) as ExternalAuditImportDraft

describe('useImportReviewDerived', () => {
  it('counts pending, promoteable, and approved drafts', () => {
    const drafts = [
      draft({ id: 1, status: 'draft' }),
      draft({ id: 2, status: 'accepted' }),
      draft({ id: 3, status: 'accepted', promoted_finding_id: 99 }),
      draft({ id: 4, status: 'promoted', promoted_finding_id: 100 }),
    ]
    const { result } = renderHook(() => useImportReviewDerived(null, null, drafts, null))
    expect(result.current.pendingDraftCount).toBe(1)
    expect(result.current.promoteableCount).toBe(1)
    expect(result.current.approvedCount).toBe(3)
  })

  it('counts risk candidates with the materialization type and severity gate', () => {
    const drafts = [
      draft({ id: 1, status: 'accepted', finding_type: 'nonconformity', severity: 'medium' }),
      draft({ id: 2, status: 'accepted', finding_type: 'nonconformity', severity: 'low' }),
      draft({ id: 3, status: 'accepted', finding_type: 'positive_practice', severity: 'critical' }),
      draft({ id: 4, status: 'accepted', finding_type: 'observation', severity: 'high' }),
      draft({ id: 5, status: 'rejected', finding_type: 'major_nonconformity', severity: 'critical' }),
    ]

    const { result } = renderHook(() => useImportReviewDerived(null, null, drafts, null))

    expect(result.current.acceptedActionCandidates).toBe(2)
    expect(result.current.acceptedRiskCandidates).toBe(1)
  })
})
