import { describe, expect, it, vi } from 'vitest'
import { createPlanetMarkApi } from './planetMarkClient'

function mockApi() {
  return {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
    put: vi.fn(),
  }
}

describe('createPlanetMarkApi', () => {
  it('getDashboard hits planet-mark dashboard', () => {
    const api = mockApi()
    createPlanetMarkApi(api as never).getDashboard()
    expect(api.get).toHaveBeenCalledWith('/api/v1/planet-mark/dashboard')
  })

  it('listYears hits years collection', () => {
    const api = mockApi()
    createPlanetMarkApi(api as never).listYears()
    expect(api.get).toHaveBeenCalledWith('/api/v1/planet-mark/years')
  })

  it('getYear hits year by id', () => {
    const api = mockApi()
    createPlanetMarkApi(api as never).getYear(42)
    expect(api.get).toHaveBeenCalledWith('/api/v1/planet-mark/years/42')
  })
})
