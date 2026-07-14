import { describe, expect, it, vi } from 'vitest'
import { createEngineersApi } from './engineersClient'

describe('createEngineersApi', () => {
  it('getByUserMe hits /api/v1/engineers/by-user/me', () => {
    const api = { get: vi.fn() }
    createEngineersApi(api as never).getByUserMe()
    expect(api.get).toHaveBeenCalledWith('/api/v1/engineers/by-user/me')
  })
})
