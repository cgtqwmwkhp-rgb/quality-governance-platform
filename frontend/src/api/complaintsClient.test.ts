import { describe, expect, it, vi } from 'vitest'
import { createComplaintsApi } from './complaintsClient'

function mockApi() {
  return {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  }
}

describe('createComplaintsApi', () => {
  it('list uses trailing-slash complaints collection path', () => {
    const api = mockApi()
    createComplaintsApi(api as never).list(2, 25)
    expect(api.get).toHaveBeenCalledWith('/api/v1/complaints/?page=2&page_size=25')
  })

  it('get and update use resource paths', () => {
    const api = mockApi()
    const complaints = createComplaintsApi(api as never)
    complaints.get(9)
    complaints.update(9, { status: 'closed' })
    expect(api.get).toHaveBeenCalledWith('/api/v1/complaints/9')
    expect(api.patch).toHaveBeenCalledWith('/api/v1/complaints/9', { status: 'closed' })
  })

  it('running-sheet helpers match OpenAPI nested paths', () => {
    const api = mockApi()
    const complaints = createComplaintsApi(api as never)
    complaints.listRunningSheet(3)
    complaints.addRunningSheetEntry(3, { content: 'note', entry_type: 'update' })
    complaints.deleteRunningSheetEntry(3, 7)
    expect(api.get).toHaveBeenCalledWith('/api/v1/complaints/3/running-sheet')
    expect(api.post).toHaveBeenCalledWith('/api/v1/complaints/3/running-sheet', {
      content: 'note',
      entry_type: 'update',
    })
    expect(api.delete).toHaveBeenCalledWith('/api/v1/complaints/3/running-sheet/7')
  })

  it('listInvestigations nests under the complaint id', () => {
    const api = mockApi()
    createComplaintsApi(api as never).listInvestigations(4, 1, 10)
    expect(api.get).toHaveBeenCalledWith(
      '/api/v1/complaints/4/investigations?page=1&page_size=10',
    )
  })
})
