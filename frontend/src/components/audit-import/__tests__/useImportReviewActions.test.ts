import { describe, expect, it, vi } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useImportReviewActions } from '../useImportReviewActions'

vi.mock('../../../api/client', () => ({
  externalAuditImportsApi: {
    reviewDraft: vi.fn(),
    bulkReviewJob: vi.fn(),
    promoteJob: vi.fn(),
    queueJob: vi.fn(),
    processJob: vi.fn(),
    getReconciliation: vi.fn(),
  },
  getApiErrorMessage: () => 'error',
}))

describe('useImportReviewActions', () => {
  it('opens promote confirm only when promoteable drafts exist', () => {
    const { result } = renderHook(() =>
      useImportReviewActions({
        job: { id: 1, status: 'ready' } as any,
        setJob: vi.fn(),
        setDrafts: vi.fn(),
        setReconciliation: vi.fn(),
        setError: vi.fn(),
        setQueueNotice: vi.fn(),
        setReconciliationNotice: vi.fn(),
        setPromotionFailedDrafts: vi.fn(),
        setIsProcessing: vi.fn(),
        load: vi.fn(),
        promoteableCount: 2,
        pendingDraftCount: 0,
      }),
    )
    act(() => {
      result.current.handlePromoteClick()
    })
    expect(result.current.showPromoteConfirm).toBe(true)
  })

  it('does not open promote confirm when none promoteable', () => {
    const { result } = renderHook(() =>
      useImportReviewActions({
        job: { id: 1, status: 'ready' } as any,
        setJob: vi.fn(),
        setDrafts: vi.fn(),
        setReconciliation: vi.fn(),
        setError: vi.fn(),
        setQueueNotice: vi.fn(),
        setReconciliationNotice: vi.fn(),
        setPromotionFailedDrafts: vi.fn(),
        setIsProcessing: vi.fn(),
        load: vi.fn(),
        promoteableCount: 0,
        pendingDraftCount: 0,
      }),
    )
    act(() => {
      result.current.handlePromoteClick()
    })
    expect(result.current.showPromoteConfirm).toBe(false)
  })
})
