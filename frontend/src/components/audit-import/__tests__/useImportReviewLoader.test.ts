import { describe, expect, it, vi, beforeEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { useImportReviewLoader } from '../useImportReviewLoader'

vi.mock('../../../api/client', () => ({
  auditsApi: {
    getRunDetail: vi.fn().mockResolvedValue({ data: { id: 10, template_name: 'T' } }),
  },
  externalAuditImportsApi: {
    getJob: vi.fn().mockResolvedValue({
      data: { id: 5, audit_run_id: 10, status: 'ready_for_review' },
    }),
    getLatestJobForRun: vi.fn(),
    listDrafts: vi.fn().mockResolvedValue({ data: [] }),
    getReconciliation: vi.fn().mockResolvedValue({ data: null }),
    processJob: vi.fn(),
  },
  getApiErrorMessage: vi.fn((e) => String(e)),
}))

describe('useImportReviewLoader', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('loads job and drafts for a jobId', async () => {
    const { result } = renderHook(() => useImportReviewLoader(5, 10, null))
    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.job?.id).toBe(5)
    expect(result.current.error).toBeNull()
    expect(result.current.drafts).toEqual([])
  })

  it('sets missing reference error when ids absent', async () => {
    const { result } = renderHook(() => useImportReviewLoader(NaN, NaN, null))
    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.error).toBe('Missing import job reference.')
  })
})
