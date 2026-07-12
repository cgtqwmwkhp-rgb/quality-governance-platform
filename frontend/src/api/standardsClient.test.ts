import { describe, expect, it, vi } from 'vitest'
import { createStandardsApi } from './standardsClient'

function mockApi() {
  return {
    get: vi.fn().mockResolvedValue({ data: {} }),
    post: vi.fn(),
    put: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  }
}

describe('createStandardsApi', () => {
  it('lists standards via GET with pagination defaults', async () => {
    const api = mockApi()
    const standardsApi = createStandardsApi(api as never)
    await standardsApi.list()
    await standardsApi.list(2, 25)
    expect(api.get).toHaveBeenCalledWith('/api/v1/standards/?page=1&page_size=10')
    expect(api.get).toHaveBeenCalledWith('/api/v1/standards/?page=2&page_size=25')
  })

  it('covers get/clauses/controls/compliance-score paths', async () => {
    const api = mockApi()
    const standardsApi = createStandardsApi(api as never)
    await standardsApi.get(3)
    await standardsApi.getClauses(3)
    await standardsApi.getControls(3)
    await standardsApi.getComplianceScore(3)
    expect(api.get).toHaveBeenCalledWith('/api/v1/standards/3')
    expect(api.get).toHaveBeenCalledWith('/api/v1/standards/3/clauses')
    expect(api.get).toHaveBeenCalledWith('/api/v1/standards/3/controls')
    expect(api.get).toHaveBeenCalledWith('/api/v1/standards/3/compliance-score')
  })
})
