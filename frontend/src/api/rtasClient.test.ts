import { describe, expect, it, vi } from 'vitest'
import { createRtasApi } from './rtasClient'

function mockApi() {
  return {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  }
}

describe('createRtasApi', () => {
  it('list uses trailing-slash rtas collection path', () => {
    const api = mockApi()
    createRtasApi(api as never).list(2, 25)
    expect(api.get).toHaveBeenCalledWith('/api/v1/rtas/?page=2&page_size=25')
  })

  it('get and update use resource paths', () => {
    const api = mockApi()
    const rtas = createRtasApi(api as never)
    rtas.get(9)
    rtas.update(9, { status: 'closed' })
    expect(api.get).toHaveBeenCalledWith('/api/v1/rtas/9')
    expect(api.patch).toHaveBeenCalledWith('/api/v1/rtas/9', { status: 'closed' })
  })

  it('running-sheet helpers match OpenAPI nested paths', () => {
    const api = mockApi()
    const rtas = createRtasApi(api as never)
    rtas.listRunningSheet(3)
    rtas.addRunningSheetEntry(3, { content: 'note', entry_type: 'update' })
    rtas.deleteRunningSheetEntry(3, 7)
    expect(api.get).toHaveBeenCalledWith('/api/v1/rtas/3/running-sheet')
    expect(api.post).toHaveBeenCalledWith('/api/v1/rtas/3/running-sheet', {
      content: 'note',
      entry_type: 'update',
    })
    expect(api.delete).toHaveBeenCalledWith('/api/v1/rtas/3/running-sheet/7')
  })

  it('listInvestigations nests under the rta id', () => {
    const api = mockApi()
    createRtasApi(api as never).listInvestigations(4, 1, 10)
    expect(api.get).toHaveBeenCalledWith('/api/v1/rtas/4/investigations?page=1&page_size=10')
  })
})
