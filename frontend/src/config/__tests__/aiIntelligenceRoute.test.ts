import { afterEach, describe, expect, it, vi } from 'vitest'

const detectEnvironment = vi.fn()

vi.mock('../apiBase', () => ({
  detectEnvironment: () => detectEnvironment(),
}))

describe('isAIIntelligenceRouteEnabled', () => {
  afterEach(() => {
    vi.resetModules()
    vi.unstubAllEnvs()
    detectEnvironment.mockReset()
  })

  async function loadGate() {
    const mod = await import('../aiIntelligenceRoute')
    return mod.isAIIntelligenceRouteEnabled
  }

  it('defaults to off when the flag is absent, in every environment', async () => {
    for (const environment of ['development', 'staging', 'production']) {
      detectEnvironment.mockReturnValue(environment)

      const isAIIntelligenceRouteEnabled = await loadGate()
      expect(isAIIntelligenceRouteEnabled()).toBe(false)
    }
  })

  it('returns false in production even when the explicit flag is set', async () => {
    detectEnvironment.mockReturnValue('production')
    vi.stubEnv('VITE_ENABLE_AI_INTELLIGENCE_ROUTE', 'true')

    const isAIIntelligenceRouteEnabled = await loadGate()
    expect(isAIIntelligenceRouteEnabled()).toBe(false)
  })

  it('returns false in non-production when the explicit flag is false', async () => {
    detectEnvironment.mockReturnValue('staging')
    vi.stubEnv('VITE_ENABLE_AI_INTELLIGENCE_ROUTE', 'false')

    const isAIIntelligenceRouteEnabled = await loadGate()
    expect(isAIIntelligenceRouteEnabled()).toBe(false)
  })

  it('rejects unrecognised flag values rather than treating them as truthy', async () => {
    detectEnvironment.mockReturnValue('development')
    vi.stubEnv('VITE_ENABLE_AI_INTELLIGENCE_ROUTE', 'enabled')

    const isAIIntelligenceRouteEnabled = await loadGate()
    expect(isAIIntelligenceRouteEnabled()).toBe(false)
  })

  it('returns true only when non-production and explicit flag is true', async () => {
    detectEnvironment.mockReturnValue('development')
    vi.stubEnv('VITE_ENABLE_AI_INTELLIGENCE_ROUTE', 'true')

    const isAIIntelligenceRouteEnabled = await loadGate()
    expect(isAIIntelligenceRouteEnabled()).toBe(true)
  })

  it('accepts staging + flag=1 as enabled', async () => {
    detectEnvironment.mockReturnValue('staging')
    vi.stubEnv('VITE_ENABLE_AI_INTELLIGENCE_ROUTE', '1')

    const isAIIntelligenceRouteEnabled = await loadGate()
    expect(isAIIntelligenceRouteEnabled()).toBe(true)
  })
})
