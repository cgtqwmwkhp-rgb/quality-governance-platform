import { describe, expect, it, vi } from 'vitest'
import { createLookupsApi } from './lookupsClient'

function mockApi() {
  return {
    get: vi.fn().mockResolvedValue({ data: { items: [], total: 0 } }),
    post: vi.fn().mockResolvedValue({ data: { id: 1 } }),
    patch: vi.fn().mockResolvedValue({ data: { id: 1 } }),
    delete: vi.fn().mockResolvedValue({ data: undefined }),
  }
}

describe('createLookupsApi', () => {
  it('list builds category path with active filter by default', async () => {
    const api = mockApi()
    await createLookupsApi(api as never).list('roles')
    expect(api.get).toHaveBeenCalledWith('/api/v1/admin/config/lookup/roles?is_active=true')

    await createLookupsApi(api as never).list('roles', false)
    expect(api.get).toHaveBeenCalledWith('/api/v1/admin/config/lookup/roles')
  })

  it('create injects path category into the body', async () => {
    const api = mockApi()
    const lookups = createLookupsApi(api as never)
    const payload = { code: 'ops', label: 'Ops', is_active: true, display_order: 1 }

    await lookups.create('roles', payload)
    await lookups.update('roles', 9, { label: 'Operations' })
    await lookups.delete('roles', 9)

    expect(api.post).toHaveBeenCalledWith('/api/v1/admin/config/lookup/roles', {
      ...payload,
      category: 'roles',
    })
    expect(api.patch).toHaveBeenCalledWith('/api/v1/admin/config/lookup/roles/9', {
      label: 'Operations',
    })
    expect(api.delete).toHaveBeenCalledWith('/api/v1/admin/config/lookup/roles/9')
  })
})
