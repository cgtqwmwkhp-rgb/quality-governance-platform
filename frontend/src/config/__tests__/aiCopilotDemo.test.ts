import { afterEach, describe, expect, it, vi } from 'vitest'

// The gate deliberately holds no environment condition any more: a production bake is
// opted in exactly like any other. Nothing here mocks an environment, so if one is
// reintroduced via detectEnvironment this mock makes it fail loudly rather than
// silently reinstating the old production block.
vi.mock('../apiBase', () => ({
  detectEnvironment: () => {
    throw new Error('the copilot demo gate must not depend on the detected environment')
  },
}))

describe('isAICopilotDemoEnabled', () => {
  afterEach(() => {
    vi.resetModules()
    vi.unstubAllEnvs()
  })

  async function loadGate(flag?: string) {
    if (flag !== undefined) {
      vi.stubEnv('VITE_ENABLE_AI_COPILOT_DEMO', flag)
    }
    const mod = await import('../aiCopilotDemo')
    return mod.isAICopilotDemoEnabled
  }

  it('defaults to off when the flag is absent', async () => {
    const isAICopilotDemoEnabled = await loadGate()
    expect(isAICopilotDemoEnabled()).toBe(false)
  })

  it.each(['', ' ', 'false', '0', 'no', 'maybe'])(
    'stays off for the unrecognised flag value %j',
    async (value) => {
      const isAICopilotDemoEnabled = await loadGate(value)
      expect(isAICopilotDemoEnabled()).toBe(false)
    },
  )

  it.each(['true', 'TRUE', ' true ', '1', 'yes'])(
    'is on for the truthy flag value %j the deploy workflows bake',
    async (value) => {
      const isAICopilotDemoEnabled = await loadGate(value)
      expect(isAICopilotDemoEnabled()).toBe(true)
    },
  )

  it('honours the flag in a production bake', async () => {
    vi.stubEnv('VITE_ENVIRONMENT', 'production')
    vi.stubEnv('VITE_API_URL', 'https://app-qgp-prod.azurewebsites.net')

    const isAICopilotDemoEnabled = await loadGate('true')
    expect(isAICopilotDemoEnabled()).toBe(true)
  })

  it('stays off in a production bake when the flag is not set', async () => {
    vi.stubEnv('VITE_ENVIRONMENT', 'production')
    vi.stubEnv('VITE_API_URL', 'https://app-qgp-prod.azurewebsites.net')

    const isAICopilotDemoEnabled = await loadGate()
    expect(isAICopilotDemoEnabled()).toBe(false)
  })
})
