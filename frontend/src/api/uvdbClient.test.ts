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
    await uvdb.getISOMapping()

    expect(get).toHaveBeenCalledWith('/api/v1/uvdb/dashboard')
    expect(get).toHaveBeenCalledWith('/api/v1/uvdb/protocol')
    expect(get).toHaveBeenCalledWith('/api/v1/uvdb/sections')
    expect(get).toHaveBeenCalledWith('/api/v1/uvdb/iso-mapping')
  })

  it('lists audits with optional filters', async () => {
    const get = vi.fn().mockResolvedValue({ data: { audits: [] } })
    const api = { get } as any
    const uvdb = createUvdbApi(api)
    await uvdb.listAudits({ status: 'open', skip: 0, limit: 10 })
    expect(get.mock.calls[0][0]).toContain('/api/v1/uvdb/audits')
    expect(get.mock.calls[0][0]).toContain('status=open')
  })
})
