import { describe, expect, it, vi } from 'vitest'
import { createUsersApi } from './usersClient'

function mockApi() {
  return {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  }
}

describe('createUsersApi', () => {
  it('search encodes query', () => {
    const api = mockApi()
    createUsersApi(api as never).search('ada lovelace')
    expect(api.get).toHaveBeenCalledWith('/api/v1/users/search/?q=ada%20lovelace')
  })

  it('list builds optional filters', () => {
    const api = mockApi()
    createUsersApi(api as never).list(2, 25, { search: 'x', department: 'ops', is_active: true })
    expect(api.get).toHaveBeenCalledWith(
      '/api/v1/users/?page=2&page_size=25&search=x&department=ops&is_active=true',
      undefined,
    )
  })

  it('get/create/update/delete and roles hit expected paths', () => {
    const api = mockApi()
    const users = createUsersApi(api as never)
    users.get(9)
    users.create({ email: 'a@b.c', first_name: 'A', last_name: 'B' })
    users.update(9, { first_name: 'C' })
    users.delete(9)
    users.listRoles()
    users.createRole({ name: 'r', permissions: ['p'] })
    users.updateRole(3, { name: 'r2' })
    expect(api.get).toHaveBeenCalledWith('/api/v1/users/9')
    expect(api.post).toHaveBeenCalledWith('/api/v1/users/', {
      email: 'a@b.c',
      first_name: 'A',
      last_name: 'B',
    })
    expect(api.patch).toHaveBeenCalledWith('/api/v1/users/9', { first_name: 'C' })
    expect(api.delete).toHaveBeenCalledWith('/api/v1/users/9')
    expect(api.get).toHaveBeenCalledWith('/api/v1/users/roles/', undefined)
    expect(api.post).toHaveBeenCalledWith('/api/v1/users/roles/', { name: 'r', permissions: ['p'] })
    expect(api.patch).toHaveBeenCalledWith('/api/v1/users/roles/3', { name: 'r2' })
  })
})
