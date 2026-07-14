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

  it('reports queued promotion honestly and relies on polling', async () => {
    const promoteJob = vi.mocked((await import('../../../api/client')).externalAuditImportsApi.promoteJob)
    promoteJob.mockResolvedValue({ data: { id: 1, status: 'promoting' } } as never)
    const setJob = vi.fn()
    const load = vi.fn()
    const { result } = renderHook(() =>
      useImportReviewActions({
        job: { id: 1, status: 'review_required' } as any,
        setJob,
        setDrafts: vi.fn(),
        setReconciliation: vi.fn(),
        setError: vi.fn(),
        setQueueNotice: vi.fn(),
        setReconciliationNotice: vi.fn(),
        setPromotionFailedDrafts: vi.fn(),
        setIsProcessing: vi.fn(),
        load,
        promoteableCount: 2,
        pendingDraftCount: 0,
      }),
    )

    await act(async () => {
      await result.current.handlePromoteConfirm()
    })

    expect(setJob).toHaveBeenCalledWith({ id: 1, status: 'promoting' })
    expect(load).not.toHaveBeenCalled()
    expect(result.current.successMessage).toMatch(/Promotion started/i)
  })
})
