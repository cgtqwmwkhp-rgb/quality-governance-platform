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

  it('analytics namespace aliases flat wdp methods', () => {
    const api = mockApi()
    const workforce = createWorkforceApi(api as never)
    workforce.analytics.getSummary()
    workforce.analytics.getEngineerMatrix()
    workforce.analytics.getTrends()
    expect(api.get).toHaveBeenCalledWith('/api/v1/wdp-analytics/summary')
    expect(api.get).toHaveBeenCalledWith('/api/v1/wdp-analytics/engineer-matrix')
    expect(api.get).toHaveBeenCalledWith('/api/v1/wdp-analytics/trends')
  })

  it('trainingTickets list/get/create/update/delete paths', () => {
    const api = mockApi()
    const workforce = createWorkforceApi(api as never)
    workforce.trainingTickets.list({ engineer_id: 3, page: 1 })
    workforce.trainingTickets.get(9)
    workforce.trainingTickets.create({
      engineer_id: 3,
      scheme: 'CSCS',
      ticket_number: 'ABC-1',
    })
    workforce.trainingTickets.update(9, { verify_state: 'verified' })
    workforce.trainingTickets.delete(9)
    expect(api.get).toHaveBeenCalledWith('/api/v1/training-tickets/', {
      params: { engineer_id: 3, page: 1 },
    })
    expect(api.get).toHaveBeenCalledWith('/api/v1/training-tickets/9')
    expect(api.post).toHaveBeenCalledWith('/api/v1/training-tickets/', {
      engineer_id: 3,
      scheme: 'CSCS',
      ticket_number: 'ABC-1',
    })
    expect(api.patch).toHaveBeenCalledWith('/api/v1/training-tickets/9', {
      verify_state: 'verified',
    })
    expect(api.delete).toHaveBeenCalledWith('/api/v1/training-tickets/9')
  })

  it('competencyRequirements list/get/create/update/allocate paths', () => {
    const api = mockApi()
    const workforce = createWorkforceApi(api as never)
    workforce.competencyRequirements.list({ asset_type_id: 2 })
    workforce.competencyRequirements.get(4)
    workforce.competencyRequirements.create({
      asset_type_id: 2,
      template_id: 1,
      name: 'MEWP competence',
    })
    workforce.competencyRequirements.update(4, { reassessment_interval_days: 180 })
    workforce.competencyRequirements.allocate(4, {
      engineer_ids: [10, 11],
      match_site: true,
      due_days: 30,
    })
    expect(api.get).toHaveBeenCalledWith('/api/v1/competency-requirements/', {
      params: { asset_type_id: 2 },
    })
    expect(api.get).toHaveBeenCalledWith('/api/v1/competency-requirements/4')
    expect(api.post).toHaveBeenCalledWith('/api/v1/competency-requirements/', {
      asset_type_id: 2,
      template_id: 1,
      name: 'MEWP competence',
    })
    expect(api.patch).toHaveBeenCalledWith('/api/v1/competency-requirements/4', {
      reassessment_interval_days: 180,
    })
    expect(api.post).toHaveBeenCalledWith('/api/v1/competency-requirements/4/allocate', {
      engineer_ids: [10, 11],
      match_site: true,
      due_days: 30,
    })
  })
})
