import { describe, expect, it, vi } from 'vitest'
import { createWorkflowsApi } from './workflowsClient'

function mockApi() {
  return {
    get: vi.fn(),
    post: vi.fn(),
    delete: vi.fn(),
  }
}

describe('createWorkflowsApi', () => {
  it('getPendingApprovals hits pending approvals path', () => {
    const api = mockApi()
    createWorkflowsApi(api as never).getPendingApprovals()
    expect(api.get).toHaveBeenCalledWith('/api/v1/workflows/approvals/pending')
  })

  it('approve/reject/bulkApprove use approval action paths', () => {
    const api = mockApi()
    const w = createWorkflowsApi(api as never)
    w.approveRequest('a1', { notes: 'ok' })
    w.rejectRequest('a2', { reason: 'no' })
    w.bulkApprove(['a1', 'a2'], { notes: 'batch' })
    expect(api.post).toHaveBeenCalledWith('/api/v1/workflows/approvals/a1/approve', { notes: 'ok' })
    expect(api.post).toHaveBeenCalledWith('/api/v1/workflows/approvals/a2/reject', { reason: 'no' })
    expect(api.post).toHaveBeenCalledWith('/api/v1/workflows/approvals/bulk-approve', {
      approval_ids: ['a1', 'a2'],
      notes: 'batch',
    })
  })

  it('listInstances builds optional query params', () => {
    const api = mockApi()
    createWorkflowsApi(api as never).listInstances({ status: 'active', entity_type: 'incident' })
    expect(api.get).toHaveBeenCalledWith(
      '/api/v1/workflows/instances?status=active&entity_type=incident',
    )
  })

  it('templates/stats/delegations paths match OpenAPI', () => {
    const api = mockApi()
    const w = createWorkflowsApi(api as never)
    w.listTemplates()
    w.getStats()
    w.getDelegations()
    w.setDelegation({
      delegate_id: 3,
      start_date: '2026-01-01',
      end_date: '2026-01-31',
      reason: 'leave',
    })
    w.cancelDelegation('d9')
    expect(api.get).toHaveBeenCalledWith('/api/v1/workflows/templates')
    expect(api.get).toHaveBeenCalledWith('/api/v1/workflows/stats')
    expect(api.get).toHaveBeenCalledWith('/api/v1/workflows/delegations')
    expect(api.post).toHaveBeenCalledWith('/api/v1/workflows/delegations', {
      delegate_id: 3,
      start_date: '2026-01-01',
      end_date: '2026-01-31',
      reason: 'leave',
    })
    expect(api.delete).toHaveBeenCalledWith('/api/v1/workflows/delegations/d9')
  })
})
