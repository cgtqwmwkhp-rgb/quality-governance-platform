import { describe, expect, it, vi } from 'vitest'
import { createStandardsApi } from './standardsClient'

describe('createStandardsApi', () => {
  it('lists standards via GET', async () => {
    const get = vi.fn().mockResolvedValue({ data: { items: [], total: 0 } })
    const api = { get, post: vi.fn(), put: vi.fn(), patch: vi.fn(), delete: vi.fn() } as never
    const standardsApi = createStandardsApi(api)
    await standardsApi.list()
    expect(get).toHaveBeenCalled()
    const url = String(get.mock.calls[0][0])
    expect(url).toContain('/api/v1/standards')
  })
})
