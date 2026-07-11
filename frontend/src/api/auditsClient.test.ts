import { describe, expect, it, vi } from 'vitest'
import { createAuditsApi } from './auditsClient'

function mockApi() {
  return {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  }
}

describe('createAuditsApi', () => {
  it('listTemplates builds query params', () => {
    const api = mockApi()
    createAuditsApi(api as never).listTemplates(2, 25, { search: 'iso', is_published: true })
    expect(api.get).toHaveBeenCalledWith(
      '/api/v1/audits/templates?page=2&page_size=25&is_published=true&search=iso',
    )
  })

  it('run lifecycle paths match OpenAPI', () => {
    const api = mockApi()
    const audits = createAuditsApi(api as never)
    audits.listRuns(1, 10)
    audits.startRun(4)
    audits.completeRun(4)
    expect(api.get).toHaveBeenCalledWith('/api/v1/audits/runs?page=1&page_size=10')
    expect(api.post).toHaveBeenCalledWith('/api/v1/audits/runs/4/start')
    expect(api.post).toHaveBeenCalledWith('/api/v1/audits/runs/4/complete')
  })

  it('findings list includes optional run_id', () => {
    const api = mockApi()
    createAuditsApi(api as never).listFindings(1, 10, 9)
    expect(api.get).toHaveBeenCalledWith('/api/v1/audits/findings?page=1&page_size=10&run_id=9')
  })
})
