import { describe, expect, it, vi } from 'vitest'
import { createSignaturesApi } from './signaturesClient'

function mockApi() {
  return {
    get: vi.fn(),
    post: vi.fn(),
  }
}

describe('createSignaturesApi', () => {
  it('list builds status/limit query params with defaults', () => {
    const api = mockApi()
    createSignaturesApi(api as never).list('pending', 10)
    expect(api.get).toHaveBeenCalledWith('/api/v1/signatures/requests?limit=10&status=pending')

    createSignaturesApi(api as never).list()
    expect(api.get).toHaveBeenCalledWith('/api/v1/signatures/requests?limit=50')
  })

  it('get/pending/stats/templates paths match OpenAPI', () => {
    const api = mockApi()
    const signatures = createSignaturesApi(api as never)
    signatures.get(9)
    signatures.getPending()
    signatures.getStats()
    signatures.listTemplates()
    signatures.getAuditLog(9)
    expect(api.get).toHaveBeenCalledWith('/api/v1/signatures/requests/9')
    expect(api.get).toHaveBeenCalledWith('/api/v1/signatures/requests/pending')
    expect(api.get).toHaveBeenCalledWith('/api/v1/signatures/stats')
    expect(api.get).toHaveBeenCalledWith('/api/v1/signatures/templates')
    expect(api.get).toHaveBeenCalledWith('/api/v1/signatures/requests/9/audit-log')
  })

  it('create/send/void/createTemplate post to signatures actions', () => {
    const api = mockApi()
    const signatures = createSignaturesApi(api as never)
    const payload = {
      title: 'NDA',
      document_type: 'policy',
      signers: [{ email: 'a@b.c', name: 'A' }],
    }
    signatures.create(payload)
    signatures.send(3)
    signatures.void(3, 'cancelled')
    signatures.createTemplate({ name: 'tmpl' })
    expect(api.post).toHaveBeenCalledWith('/api/v1/signatures/requests', payload)
    expect(api.post).toHaveBeenCalledWith('/api/v1/signatures/requests/3/send')
    expect(api.post).toHaveBeenCalledWith('/api/v1/signatures/requests/3/void', {
      reason: 'cancelled',
    })
    expect(api.post).toHaveBeenCalledWith('/api/v1/signatures/templates', { name: 'tmpl' })
  })
})
