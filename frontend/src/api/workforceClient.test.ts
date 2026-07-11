import { describe, expect, it, vi } from 'vitest'
import { createWorkforceApi } from './workforceClient'

function mockApi() {
  return {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  }
}

describe('createWorkforceApi', () => {
  it('assessment lifecycle paths match OpenAPI', () => {
    const api = mockApi()
    const workforce = createWorkforceApi(api as never)
    workforce.listAssessments({ page: 1, page_size: 10 })
    workforce.startAssessment('run-1')
    workforce.completeAssessment('run-1')
    expect(api.get).toHaveBeenCalledWith('/api/v1/assessments/', {
      params: { page: 1, page_size: 10 },
    })
    expect(api.post).toHaveBeenCalledWith('/api/v1/assessments/run-1/start')
    expect(api.post).toHaveBeenCalledWith('/api/v1/assessments/run-1/complete')
  })

  it('induction list and engineer competencies paths', () => {
    const api = mockApi()
    const workforce = createWorkforceApi(api as never)
    workforce.listInductions({ page: 2 })
    workforce.getCompetencies(7)
    expect(api.get).toHaveBeenCalledWith('/api/v1/inductions/', { params: { page: 2 } })
    expect(api.get).toHaveBeenCalledWith('/api/v1/engineers/7/competencies')
  })

  it('wdp analytics summary path', () => {
    const api = mockApi()
    createWorkforceApi(api as never).getWdpSummary()
    expect(api.get).toHaveBeenCalledWith('/api/v1/wdp-analytics/summary')
  })
})
