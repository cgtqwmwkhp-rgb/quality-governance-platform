import { afterEach, describe, expect, it, vi } from 'vitest'

const detectEnvironment = vi.fn()

vi.mock('../apiBase', () => ({
  detectEnvironment: () => detectEnvironment(),
}))

describe('isAICopilotDemoEnabled', () => {
  afterEach(() => {
    vi.resetModules()
    vi.unstubAllEnvs()
    detectEnvironment.mockReset()
  })

  async function loadGate() {
    const mod = await import('../aiCopilotDemo')
    return mod.isAICopilotDemoEnabled
  }

  it('defaults to off when the flag is absent, in every environment', async () => {
    for (const environment of ['development', 'staging', 'production']) {
      detectEnvironment.mockReturnValue(environment)

      const isAICopilotDemoEnabled = await loadGate()
      expect(isAICopilotDemoEnabled()).toBe(false)
    }
  })

  it('returns false in production even when the explicit flag is set', async () => {
    detectEnvironment.mockReturnValue('production')
    vi.stubEnv('VITE_ENABLE_AI_COPILOT_DEMO', 'true')

    const isAICopilotDemoEnabled = await loadGate()
    expect(isAICopilotDemoEnabled()).toBe(false)
  })

  it('returns false in non-production when the explicit flag is false', async () => {
    detectEnvironment.mockReturnValue('staging')
    vi.stubEnv('VITE_ENABLE_AI_COPILOT_DEMO', 'false')

    const isAICopilotDemoEnabled = await loadGate()
    expect(isAICopilotDemoEnabled()).toBe(false)
  })

  it('returns true only when non-production and explicit flag is true', async () => {
    detectEnvironment.mockReturnValue('development')
    vi.stubEnv('VITE_ENABLE_AI_COPILOT_DEMO', 'true')

    const isAICopilotDemoEnabled = await loadGate()
    expect(isAICopilotDemoEnabled()).toBe(true)
  })

  it('accepts staging + flag=1 as enabled', async () => {
    detectEnvironment.mockReturnValue('staging')
    vi.stubEnv('VITE_ENABLE_AI_COPILOT_DEMO', '1')

    const isAICopilotDemoEnabled = await loadGate()
    expect(isAICopilotDemoEnabled()).toBe(true)
  })
})
