import { describe, expect, it, vi } from 'vitest'
import { createPoliciesApi } from './policiesClient'

function mockApi() {
  return {
    get: vi.fn(),
    post: vi.fn(),
  }
}

describe('createPoliciesApi', () => {
  it('list uses policies collection without trailing slash', () => {
    const api = mockApi()
    createPoliciesApi(api as never).list(1, 50)
    expect(api.get).toHaveBeenCalledWith('/api/v1/policies?page=1&page_size=50')
  })

  it('create posts to policies collection', () => {
    const api = mockApi()
    const body = { title: 'H&S', document_type: 'policy' }
    createPoliciesApi(api as never).create(body)
    expect(api.post).toHaveBeenCalledWith('/api/v1/policies', body)
  })

  it('get uses policy resource path', () => {
    const api = mockApi()
    createPoliciesApi(api as never).get(12)
    expect(api.get).toHaveBeenCalledWith('/api/v1/policies/12')
  })
})
