import { describe, expect, it, vi } from 'vitest'
import { createRisksApi } from './risksClient'

function mockApi() {
  return {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  }
}

describe('createRisksApi', () => {
  it('list uses trailing-slash risks collection path with optional search', () => {
    const api = mockApi()
    createRisksApi(api as never).list(1, 10, 'fire')
    expect(api.get).toHaveBeenCalledWith('/api/v1/risks/?page=1&page_size=10&search=fire')
  })

  it('create and get use collection/resource paths', () => {
    const api = mockApi()
    const risks = createRisksApi(api as never)
    risks.create({
      title: 't',
      description: 'd',
      category: 'ops',
      likelihood: 2,
      impact: 3,
    })
    risks.get(5)
    expect(api.post).toHaveBeenCalledWith('/api/v1/risks/', {
      title: 't',
      description: 'd',
      category: 'ops',
      likelihood: 2,
      impact: 3,
    })
    expect(api.get).toHaveBeenCalledWith('/api/v1/risks/5')
  })
})
