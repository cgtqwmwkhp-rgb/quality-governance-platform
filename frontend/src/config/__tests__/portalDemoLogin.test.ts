import { afterEach, describe, expect, it, vi } from 'vitest'

const detectEnvironment = vi.fn()

vi.mock('../apiBase', () => ({
  detectEnvironment: () => detectEnvironment(),
}))

describe('isPortalDemoLoginEnabled', () => {
  afterEach(() => {
    vi.resetModules()
    vi.unstubAllEnvs()
    detectEnvironment.mockReset()
  })

  async function loadGate() {
    const mod = await import('../portalDemoLogin')
    return mod.isPortalDemoLoginEnabled
  }

  it('returns false in production even when the explicit flag is set', async () => {
    detectEnvironment.mockReturnValue('production')
    vi.stubEnv('VITE_ENABLE_PORTAL_DEMO_LOGIN', 'true')

    const isPortalDemoLoginEnabled = await loadGate()
    expect(isPortalDemoLoginEnabled()).toBe(false)
  })

  it('returns false in non-production when the explicit flag is unset', async () => {
    detectEnvironment.mockReturnValue('development')
    vi.stubEnv('VITE_ENABLE_PORTAL_DEMO_LOGIN', '')

    const isPortalDemoLoginEnabled = await loadGate()
    expect(isPortalDemoLoginEnabled()).toBe(false)
  })

  it('returns false in non-production when the explicit flag is false', async () => {
    detectEnvironment.mockReturnValue('staging')
    vi.stubEnv('VITE_ENABLE_PORTAL_DEMO_LOGIN', 'false')

    const isPortalDemoLoginEnabled = await loadGate()
    expect(isPortalDemoLoginEnabled()).toBe(false)
  })

  it('returns true only when non-production and explicit flag is true', async () => {
    detectEnvironment.mockReturnValue('development')
    vi.stubEnv('VITE_ENABLE_PORTAL_DEMO_LOGIN', 'true')

    const isPortalDemoLoginEnabled = await loadGate()
    expect(isPortalDemoLoginEnabled()).toBe(true)
  })

  it('accepts staging + flag=1 as enabled', async () => {
    detectEnvironment.mockReturnValue('staging')
    vi.stubEnv('VITE_ENABLE_PORTAL_DEMO_LOGIN', '1')

    const isPortalDemoLoginEnabled = await loadGate()
    expect(isPortalDemoLoginEnabled()).toBe(true)
  })
})
