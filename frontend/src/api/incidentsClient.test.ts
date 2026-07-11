import { describe, expect, it, vi } from 'vitest'
import { createIncidentsApi } from './incidentsClient'

function mockApi() {
  return {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  }
}

describe('createIncidentsApi', () => {
  it('list uses trailing-slash incidents collection path', () => {
    const api = mockApi()
    createIncidentsApi(api as never).list(2, 25)
    expect(api.get).toHaveBeenCalledWith('/api/v1/incidents/?page=2&page_size=25')
  })

  it('get and update use resource paths', () => {
    const api = mockApi()
    const incidents = createIncidentsApi(api as never)
    incidents.get(9)
    incidents.update(9, { status: 'closed' })
    expect(api.get).toHaveBeenCalledWith('/api/v1/incidents/9')
    expect(api.patch).toHaveBeenCalledWith('/api/v1/incidents/9', { status: 'closed' })
  })

  it('running-sheet helpers match OpenAPI nested paths', () => {
    const api = mockApi()
    const incidents = createIncidentsApi(api as never)
    incidents.listRunningSheet(3)
    incidents.addRunningSheetEntry(3, { content: 'note', entry_type: 'update' })
    incidents.deleteRunningSheetEntry(3, 7)
    expect(api.get).toHaveBeenCalledWith('/api/v1/incidents/3/running-sheet')
    expect(api.post).toHaveBeenCalledWith('/api/v1/incidents/3/running-sheet', {
      content: 'note',
      entry_type: 'update',
    })
    expect(api.delete).toHaveBeenCalledWith('/api/v1/incidents/3/running-sheet/7')
  })

  it('listInvestigations nests under the incident id', () => {
    const api = mockApi()
    createIncidentsApi(api as never).listInvestigations(4, 1, 10)
    expect(api.get).toHaveBeenCalledWith('/api/v1/incidents/4/investigations?page=1&page_size=10')
  })
})
