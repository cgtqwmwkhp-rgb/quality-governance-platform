import { afterEach, describe, expect, it, vi } from 'vitest'

describe('apiBase', () => {
  afterEach(() => {
    vi.unstubAllEnvs()
    vi.resetModules()
  })

  it('detectEnvironment honors explicit VITE_ENVIRONMENT', async () => {
    vi.stubEnv('VITE_ENVIRONMENT', 'staging')
    const mod = await import('./apiBase')
    expect(mod.detectEnvironment()).toBe('staging')
  })

  it('getApiBaseUrl prefers VITE_API_URL and strips trailing slash', async () => {
    vi.stubEnv('VITE_API_URL', 'https://example.test/api/')
    vi.stubEnv('VITE_ENVIRONMENT', 'development')
    const mod = await import('./apiBase')
    expect(mod.getApiBaseUrl()).toBe('https://example.test/api')
  })

  it('getApiBaseUrl upgrades http to https outside localhost', async () => {
    vi.stubEnv('VITE_API_URL', 'http://example.test')
    vi.stubEnv('VITE_ENVIRONMENT', 'development')
    const mod = await import('./apiBase')
    expect(mod.getApiBaseUrl()).toBe('https://example.test')
  })
})
