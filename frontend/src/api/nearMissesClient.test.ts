import { describe, expect, it, vi } from 'vitest'
import { createNearMissesApi } from './nearMissesClient'

function mockApi() {
  return {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  }
}

describe('createNearMissesApi', () => {
  it('list uses trailing-slash near-misses collection path', () => {
    const api = mockApi()
    createNearMissesApi(api as never).list(2, 25)
    expect(api.get).toHaveBeenCalledWith('/api/v1/near-misses/?page=2&page_size=25')
  })

  it('get and update use resource paths', () => {
    const api = mockApi()
    const nearMisses = createNearMissesApi(api as never)
    nearMisses.get(9)
    nearMisses.update(9, { status: 'closed' })
    expect(api.get).toHaveBeenCalledWith('/api/v1/near-misses/9')
    expect(api.patch).toHaveBeenCalledWith('/api/v1/near-misses/9', { status: 'closed' })
  })

  it('running-sheet helpers match OpenAPI nested paths', () => {
    const api = mockApi()
    const nearMisses = createNearMissesApi(api as never)
    nearMisses.listRunningSheet(3)
    nearMisses.addRunningSheetEntry(3, { content: 'note', entry_type: 'update' })
    nearMisses.deleteRunningSheetEntry(3, 7)
    expect(api.get).toHaveBeenCalledWith('/api/v1/near-misses/3/running-sheet')
    expect(api.post).toHaveBeenCalledWith('/api/v1/near-misses/3/running-sheet', {
      content: 'note',
      entry_type: 'update',
    })
    expect(api.delete).toHaveBeenCalledWith('/api/v1/near-misses/3/running-sheet/7')
  })
})
