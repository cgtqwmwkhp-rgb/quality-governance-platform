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
})
