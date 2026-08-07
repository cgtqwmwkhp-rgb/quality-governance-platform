import { describe, expect, it, vi } from 'vitest'
import { createDocumentGraphApi } from './documentGraphClient'

function mockApi() {
  return {
    get: vi.fn(),
    post: vi.fn(),
    delete: vi.fn(),
  }
}

describe('createDocumentGraphApi', () => {
  it('lists edges for a document, with and without filters', () => {
    const api = mockApi()
    const client = createDocumentGraphApi(api as never)

    client.listEdges(42)
    expect(api.get).toHaveBeenCalledWith('/api/v1/document-graph/documents/42/edges', {
      params: undefined,
    })

    client.listEdges(42, { edge_type: 'implements', status: 'proposed' })
    expect(api.get).toHaveBeenCalledWith('/api/v1/document-graph/documents/42/edges', {
      params: { edge_type: 'implements', status: 'proposed' },
    })
  })

  it('reads the primary-implements walk', () => {
    const api = mockApi()
    createDocumentGraphApi(api as never).getThread(42)
    expect(api.get).toHaveBeenCalledWith('/api/v1/document-graph/documents/42/thread')
  })

  it('creates an edge from the given payload', () => {
    const api = mockApi()
    const payload = {
      src_document_id: 42,
      dst_document_id: 7,
      edge_type: 'implements' as const,
      is_primary_parent: true,
      status: 'confirmed' as const,
      created_method: 'manual' as const,
    }
    createDocumentGraphApi(api as never).createEdge(payload)
    expect(api.post).toHaveBeenCalledWith('/api/v1/document-graph/edges', payload)
  })

  it('confirms, rejects and unlinks a single edge', () => {
    const api = mockApi()
    const client = createDocumentGraphApi(api as never)

    client.confirmEdge(9)
    expect(api.post).toHaveBeenCalledWith('/api/v1/document-graph/edges/9/confirm')

    client.rejectEdge(9)
    expect(api.post).toHaveBeenCalledWith('/api/v1/document-graph/edges/9/reject', {})

    client.rejectEdge(9, { rationale: 'Superseded by the new SOP' })
    expect(api.post).toHaveBeenCalledWith('/api/v1/document-graph/edges/9/reject', {
      rationale: 'Superseded by the new SOP',
    })

    client.deleteEdge(9)
    expect(api.delete).toHaveBeenCalledWith('/api/v1/document-graph/edges/9')
  })

  it('confirms a queue and reports partial failures instead of hiding them', async () => {
    const api = mockApi()
    api.post.mockImplementation((url: string) => {
      if (url.includes('/edges/2/confirm')) {
        return Promise.reject(new Error('Cannot confirm a rejected edge'))
      }
      return Promise.resolve({ data: { id: Number(url.split('/')[5]) } })
    })

    const result = await createDocumentGraphApi(api as never).confirmEdges([1, 2, 3])

    expect(result.confirmed.map((edge) => edge.id)).toEqual([1, 3])
    expect(result.failed).toHaveLength(1)
    expect(result.failed[0].edge_id).toBe(2)
    expect(api.post).toHaveBeenCalledTimes(3)
  })

  it('returns an empty result for an empty queue without calling the API', async () => {
    const api = mockApi()
    const result = await createDocumentGraphApi(api as never).confirmEdges([])
    expect(result).toEqual({ confirmed: [], failed: [] })
    expect(api.post).not.toHaveBeenCalled()
  })

  it('posts heuristic propose and reads citation staleness', () => {
    const api = mockApi()
    const client = createDocumentGraphApi(api as never)

    client.proposeHeuristics(42)
    expect(api.post).toHaveBeenCalledWith('/api/v1/document-graph/documents/42/propose')

    client.getCitationStaleness(9)
    expect(api.get).toHaveBeenCalledWith('/api/v1/document-graph/edges/9/citation-staleness')
  })

  it('lists clause documents for ISO reverse freshness', () => {
    const api = mockApi()
    createDocumentGraphApi(api as never).listClauseDocuments('9001-7.5')
    expect(api.get).toHaveBeenCalledWith(
      '/api/v1/document-graph/clauses/9001-7.5/documents',
    )
  })

  it('posts the Incident Management demo seed endpoint', () => {
    const api = mockApi()
    createDocumentGraphApi(api as never).seedIncidentManagementVertical()
    expect(api.post).toHaveBeenCalledWith(
      '/api/v1/document-graph/demo/incident-management/seed',
    )
  })
})
