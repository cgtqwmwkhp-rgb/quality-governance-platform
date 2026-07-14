import { describe, expect, it, vi } from 'vitest'
import { createKnowledgeBankApi } from './knowledgeBankClient'

function mockApi() {
  return {
    get: vi.fn(),
    post: vi.fn(),
  }
}

describe('createKnowledgeBankApi listExceptions', () => {
  it('calls exceptions with no query when params omitted', () => {
    const api = mockApi()
    createKnowledgeBankApi(api as never).listExceptions()
    expect(api.get).toHaveBeenCalledWith('/api/v1/knowledge-bank/exceptions')
  })

  it('passes entity_type and status query params when provided', () => {
    const api = mockApi()
    createKnowledgeBankApi(api as never).listExceptions({
      status: 'proposed',
      entityType: 'incident',
    })
    expect(api.get).toHaveBeenCalledWith(
      '/api/v1/knowledge-bank/exceptions?status=proposed&entity_type=incident',
    )
  })

  it('passes signal_type when provided (server filter)', () => {
    const api = mockApi()
    createKnowledgeBankApi(api as never).listExceptions({
      entityType: 'document',
      signalType: 'gap',
    })
    expect(api.get).toHaveBeenCalledWith(
      '/api/v1/knowledge-bank/exceptions?entity_type=document&signal_type=gap',
    )
  })

  it('posts reject rationale body', () => {
    const api = mockApi()
    createKnowledgeBankApi(api as never).rejectLink(9, 'Not applicable to this clause')
    expect(api.post).toHaveBeenCalledWith('/api/v1/knowledge-bank/evidence/9/reject', {
      rationale: 'Not applicable to this clause',
    })
  })

  it('omits body for legacy reject callers', () => {
    const api = mockApi()
    createKnowledgeBankApi(api as never).rejectLink(9)
    expect(api.post).toHaveBeenCalledWith('/api/v1/knowledge-bank/evidence/9/reject')
  })
})
