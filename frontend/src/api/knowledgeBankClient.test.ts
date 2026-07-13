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

  it('does not invent a signal_type query param (API gap)', () => {
    const api = mockApi()
    createKnowledgeBankApi(api as never).listExceptions({ entityType: 'document' })
    const url = String(api.get.mock.calls[0][0])
    expect(url).toContain('entity_type=document')
    expect(url).not.toContain('signal_type')
  })
})
