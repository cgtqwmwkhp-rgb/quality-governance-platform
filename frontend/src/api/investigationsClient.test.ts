import { describe, expect, it, vi } from 'vitest'
import { createInvestigationsApi } from './investigationsClient'

function mockApi() {
  return {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  }
}

describe('createInvestigationsApi', () => {
  it('list/create/get/update/autosave hit investigation paths', () => {
    const api = mockApi()
    const inv = createInvestigationsApi(api as never)
    inv.list(1, 10, 'draft')
    inv.create({
      template_id: 1,
      assigned_entity_type: 'complaint',
      assigned_entity_id: 2,
      title: 't',
    })
    inv.get(5)
    inv.update(5, { status: 'in_progress' })
    inv.autosave(5, { data: { a: 1 }, version: 3 })
    expect(api.get).toHaveBeenCalledWith('/api/v1/investigations/?page=1&page_size=10&status=draft')
    expect(api.post).toHaveBeenCalledWith('/api/v1/investigations/', {
      template_id: 1,
      assigned_entity_type: 'complaint',
      assigned_entity_id: 2,
      title: 't',
    })
    expect(api.get).toHaveBeenCalledWith('/api/v1/investigations/5')
    expect(api.patch).toHaveBeenCalledWith('/api/v1/investigations/5', { status: 'in_progress' })
    expect(api.patch).toHaveBeenCalledWith('/api/v1/investigations/5/autosave', {
      data: { a: 1 },
      version: 3,
    })
  })

  it('from-record and source-records helpers', () => {
    const api = mockApi()
    const inv = createInvestigationsApi(api as never)
    inv.createFromRecord({ source_type: 'complaint', source_id: 9, title: 'x' })
    inv.listSourceRecords('complaint', { q: 'iso', page: 2, size: 15 })
    expect(api.post).toHaveBeenCalledWith('/api/v1/investigations/from-record', {
      source_type: 'complaint',
      source_id: 9,
      title: 'x',
    })
    expect(api.get).toHaveBeenCalledWith(
      '/api/v1/investigations/source-records?source_type=complaint&q=iso&page=2&page_size=15',
    )
  })

  it('stage-1 timeline/comments/packs/closure paths', () => {
    const api = mockApi()
    const inv = createInvestigationsApi(api as never)
    inv.getTimeline(4, { page: 1, page_size: 20, type: 'status' })
    inv.getComments(4, { page: 1, page_size: 10 })
    inv.addComment(4, 'note')
    inv.getPacks(4, { page: 1, page_size: 5 })
    inv.generatePack(4, 'customer')
    inv.getClosureValidation(4)
    expect(api.get).toHaveBeenCalledWith(
      '/api/v1/investigations/4/timeline?page=1&page_size=20&event_type=status',
    )
    expect(api.get).toHaveBeenCalledWith('/api/v1/investigations/4/comments?page=1&page_size=10')
    expect(api.post).toHaveBeenCalledWith('/api/v1/investigations/4/comments', { content: 'note' })
    expect(api.get).toHaveBeenCalledWith('/api/v1/investigations/4/packs?page=1&page_size=5')
    expect(api.post).toHaveBeenCalledWith(
      '/api/v1/investigations/4/customer-pack?audience=customer',
    )
    expect(api.get).toHaveBeenCalledWith('/api/v1/investigations/4/closure-validation')
  })
})
