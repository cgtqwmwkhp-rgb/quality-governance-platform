import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('../utils/errorTracker', () => ({
  trackError: vi.fn(),
}))

describe('apiBase', () => {
  beforeEach(() => {
    vi.unstubAllEnvs()
    vi.resetModules()
  })

  afterEach(() => {
    vi.unstubAllEnvs()
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
  })

  it('detectEnvironment honors explicit VITE_ENVIRONMENT', async () => {
    vi.stubEnv('VITE_ENVIRONMENT', 'staging')
    const mod = await import('./apiBase')
    expect(mod.detectEnvironment()).toBe('staging')
  })

  it('detectEnvironment accepts production and development overrides', async () => {
    vi.stubEnv('VITE_ENVIRONMENT', 'production')
    let mod = await import('./apiBase')
    expect(mod.detectEnvironment()).toBe('production')

    vi.resetModules()
    vi.stubEnv('VITE_ENVIRONMENT', 'development')
    mod = await import('./apiBase')
    expect(mod.detectEnvironment()).toBe('development')
  })

  it('detectEnvironment ignores invalid VITE_ENVIRONMENT and infers from VITE_API_URL', async () => {
    vi.stubEnv('VITE_ENVIRONMENT', 'lab')
    vi.stubEnv('VITE_API_URL', 'https://qgp-staging-plantexpand.azurewebsites.net')
    const mod = await import('./apiBase')
    expect(mod.detectEnvironment()).toBe('staging')
  })

  it('detectEnvironment infers development/production from VITE_API_URL', async () => {
    vi.stubEnv('VITE_API_URL', 'http://localhost:8000')
    let mod = await import('./apiBase')
    expect(mod.detectEnvironment()).toBe('development')

    vi.resetModules()
    vi.stubEnv('VITE_API_URL', 'https://app-qgp-prod.azurewebsites.net')
    mod = await import('./apiBase')
    expect(mod.detectEnvironment()).toBe('production')
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
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {})
    const mod = await import('./apiBase')
    expect(mod.getApiBaseUrl()).toBe('https://example.test')
    warn.mockRestore()
  })

  it('getApiBaseUrl keeps http for localhost and falls back to API_URLS', async () => {
    vi.stubEnv('VITE_API_URL', 'http://localhost:8000/')
    vi.stubEnv('VITE_ENVIRONMENT', 'development')
    let mod = await import('./apiBase')
    expect(mod.getApiBaseUrl()).toBe('http://localhost:8000')

    vi.resetModules()
    vi.stubEnv('VITE_API_URL', '   ')
    vi.stubEnv('VITE_ENVIRONMENT', 'staging')
    mod = await import('./apiBase')
    expect(mod.getApiBaseUrl()).toBe('https://qgp-staging-plantexpand.azurewebsites.net')

    vi.resetModules()
    vi.stubEnv('VITE_API_URL', '')
    vi.stubEnv('VITE_ENVIRONMENT', 'production')
    mod = await import('./apiBase')
    expect(mod.getApiBaseUrl()).toBe('https://app-qgp-prod.azurewebsites.net')
  })

  it('getExpectedEnvironment mirrors detectEnvironment', async () => {
    vi.stubEnv('VITE_ENVIRONMENT', 'staging')
    const mod = await import('./apiBase')
    expect(mod.getExpectedEnvironment()).toBe('staging')
  })

  it('validateEnvironmentMatch skips development', async () => {
    vi.stubEnv('VITE_ENVIRONMENT', 'development')
    const mod = await import('./apiBase')
    await expect(mod.validateEnvironmentMatch()).resolves.toBeNull()
  })

  it('validateEnvironmentMatch returns mismatch message when API env differs', async () => {
    vi.stubEnv('VITE_ENVIRONMENT', 'staging')
    vi.stubEnv('VITE_API_URL', 'https://qgp-staging-plantexpand.azurewebsites.net')
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ environment: 'production' }),
      }),
    )
    const mod = await import('./apiBase')
    await expect(mod.validateEnvironmentMatch()).resolves.toMatch(/Environment mismatch/)
  })

  it('validateEnvironmentMatch returns null when API env matches', async () => {
    vi.stubEnv('VITE_ENVIRONMENT', 'staging')
    vi.stubEnv('VITE_API_URL', 'https://qgp-staging-plantexpand.azurewebsites.net')
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ environment: 'staging' }),
      }),
    )
    const mod = await import('./apiBase')
    await expect(mod.validateEnvironmentMatch()).resolves.toBeNull()
  })

  it('validateEnvironmentMatch does not block on non-ok or network errors', async () => {
    vi.stubEnv('VITE_ENVIRONMENT', 'staging')
    vi.stubEnv('VITE_API_URL', 'https://qgp-staging-plantexpand.azurewebsites.net')
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false }))
    let mod = await import('./apiBase')
    await expect(mod.validateEnvironmentMatch()).resolves.toBeNull()

    vi.resetModules()
    vi.stubEnv('VITE_ENVIRONMENT', 'staging')
    vi.stubEnv('VITE_API_URL', 'https://qgp-staging-plantexpand.azurewebsites.net')
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')))
    mod = await import('./apiBase')
    await expect(mod.validateEnvironmentMatch()).resolves.toBeNull()
  })

  it('exports module-level API_BASE_URL and CURRENT_ENVIRONMENT', async () => {
    vi.stubEnv('VITE_ENVIRONMENT', 'staging')
    vi.stubEnv('VITE_API_URL', 'https://qgp-staging-plantexpand.azurewebsites.net')
    const mod = await import('./apiBase')
    expect(mod.API_BASE_URL).toBe('https://qgp-staging-plantexpand.azurewebsites.net')
    expect(mod.CURRENT_ENVIRONMENT).toBe('staging')
  })
})
