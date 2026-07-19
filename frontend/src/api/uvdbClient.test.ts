import { describe, expect, it, vi } from 'vitest'
import { createUvdbApi } from './uvdbClient'

describe('createUvdbApi', () => {
  it('wires dashboard/protocol/sections paths', async () => {
    const get = vi.fn().mockResolvedValue({ data: {} })
    const api = { get } as any
    const uvdb = createUvdbApi(api)

    await uvdb.getDashboard()
    await uvdb.getProtocol()
    await uvdb.listSections()
    await uvdb.getSectionQuestions(2)
    await uvdb.getISOMapping()
    await uvdb.getAudit(9)
    await uvdb.getAuditResponses(9)

    expect(get).toHaveBeenCalledWith('/api/v1/uvdb/dashboard')
    expect(get).toHaveBeenCalledWith('/api/v1/uvdb/protocol')
    expect(get).toHaveBeenCalledWith('/api/v1/uvdb/sections')
    expect(get).toHaveBeenCalledWith('/api/v1/uvdb/sections/2/questions')
    expect(get).toHaveBeenCalledWith('/api/v1/uvdb/iso-mapping')
    expect(get).toHaveBeenCalledWith('/api/v1/uvdb/audits/9')
    expect(get).toHaveBeenCalledWith('/api/v1/uvdb/audits/9/responses')
  })

  it('downloads protocol pack as authenticated blob export', async () => {
    const get = vi.fn().mockResolvedValue({
      data: new Blob(['{"pack_version":"uvdb-protocol-1.0"}']),
      headers: { 'content-disposition': 'attachment; filename="uvdb-protocol-pack-2026-07-19.json"' },
    })
    const api = { get } as any
    const uvdb = createUvdbApi(api)
    const appendChild = vi.spyOn(document.body, 'appendChild').mockImplementation(() => document.body)
    const removeChild = vi.spyOn(document.body, 'removeChild').mockImplementation(() => document.body)
    const click = vi.fn()
    vi.spyOn(document, 'createElement').mockImplementation(
      () => ({ click, href: '', download: '', rel: '' }) as unknown as HTMLAnchorElement,
    )
    const createObjectURL = vi.fn(() => 'blob:uvdb-pack')
    const revokeObjectURL = vi.fn()
    vi.stubGlobal('URL', { createObjectURL, revokeObjectURL })

    await uvdb.downloadProtocolPack('json')
    expect(get).toHaveBeenCalledWith('/api/v1/uvdb/protocol/export', {
      params: { format: 'json' },
      responseType: 'blob',
    })
    expect(click).toHaveBeenCalled()

    await uvdb.downloadProtocolPack('xlsx')
    expect(get).toHaveBeenCalledWith('/api/v1/uvdb/protocol/export', {
      params: { format: 'xlsx' },
      responseType: 'blob',
    })

    appendChild.mockRestore()
    removeChild.mockRestore()
  })

  it('lists audits with optional filters and creates audits', async () => {
    const get = vi.fn().mockResolvedValue({ data: { audits: [] } })
    const post = vi.fn().mockResolvedValue({ data: { id: 1 } })
    const api = { get, post } as any
    const uvdb = createUvdbApi(api)
    await uvdb.listAudits({
      status: 'open',
      skip: 0,
      limit: 10,
      company_name: 'Acme',
      search: 'q',
      audit_type: 'B2',
      date_from: '2026-01-01',
      date_to: '2026-12-31',
      min_score: 1,
      max_score: 100,
    })
    await uvdb.listAudits()
    await uvdb.createAudit({ company_name: 'Acme', audit_type: 'B2' })
    expect(get.mock.calls[0][0]).toContain('/api/v1/uvdb/audits')
    expect(get.mock.calls[0][0]).toContain('status=open')
    expect(get.mock.calls[0][0]).toContain('company_name=Acme')
    expect(get.mock.calls[1][0]).toBe('/api/v1/uvdb/audits')
    expect(post).toHaveBeenCalledWith('/api/v1/uvdb/audits', expect.objectContaining({ company_name: 'Acme' }))
  })
})
