import { describe, expect, it, vi } from 'vitest'
import { createAuditTrailApi } from './auditTrailClient'

function mockApi() {
  return {
    get: vi.fn(),
    post: vi.fn(),
  }
}

describe('createAuditTrailApi', () => {
  it('list builds optional query params with defaults', () => {
    const api = mockApi()
    createAuditTrailApi(api as never).list({
      entity_type: 'incident',
      action: 'create',
      user_id: 1,
      date_from: '2026-01-01',
      date_to: '2026-12-31',
      page: 2,
      per_page: 10,
    })
    expect(api.get).toHaveBeenCalledWith(
      '/api/v1/audit-trail/?entity_type=incident&action=create&user_id=1&date_from=2026-01-01&date_to=2026-12-31&page=2&per_page=10',
      { suppressErrorToast: true },
    )

    createAuditTrailApi(api as never).list()
    expect(api.get).toHaveBeenCalledWith('/api/v1/audit-trail/?page=1&per_page=50', {
      suppressErrorToast: true,
    })
  })

  it('entry/entity/user/stats paths match OpenAPI', () => {
    const api = mockApi()
    const trail = createAuditTrailApi(api as never)
    trail.getEntry(1)
    trail.getByEntity('incident', '9')
    trail.getByUser(3, 14)
    trail.getStats(7)
    expect(api.get).toHaveBeenCalledWith('/api/v1/audit-trail/1')
    expect(api.get).toHaveBeenCalledWith('/api/v1/audit-trail/entity/incident/9')
    expect(api.get).toHaveBeenCalledWith('/api/v1/audit-trail/user/3?days=14')
    expect(api.get).toHaveBeenCalledWith('/api/v1/audit-trail/stats?days=7')
  })

  it('verify and exportLog post to audit-trail actions', () => {
    const api = mockApi()
    const trail = createAuditTrailApi(api as never)
    trail.verify()
    trail.exportLog({ format: 'csv', reason: 'audit' })
    expect(api.post).toHaveBeenCalledWith('/api/v1/audit-trail/verify')
    expect(api.post).toHaveBeenCalledWith('/api/v1/audit-trail/export', {
      format: 'csv',
      reason: 'audit',
    })
  })
})
