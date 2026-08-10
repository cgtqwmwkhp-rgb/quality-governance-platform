import { describe, it, expect } from 'vitest'
import {
  copilotDisclosure,
  resolveCopilotDisclosureMode,
  type CopilotDisclosureMode,
} from '../copilotDisclosure'

const MODES: CopilotDisclosureMode[] = ['unavailable', 'simulated', 'grounded']

describe('resolveCopilotDisclosureMode', () => {
  it('reports the simulator when nothing is known yet', () => {
    // The flags arrive from the network, so this is the state of the very first
    // render everywhere. Claiming grounded operation here would be a guess.
    expect(
      resolveCopilotDisclosureMode({
        unavailable: false,
        copilotOpen: false,
        inferenceOpen: false,
      }),
    ).toBe('simulated')
  })

  it('reports the simulator when the surface is open but inference is off', () => {
    expect(
      resolveCopilotDisclosureMode({
        unavailable: false,
        copilotOpen: true,
        inferenceOpen: false,
      }),
    ).toBe('simulated')
  })

  it('reports grounded only when both flags are open', () => {
    expect(
      resolveCopilotDisclosureMode({
        unavailable: false,
        copilotOpen: true,
        inferenceOpen: true,
      }),
    ).toBe('grounded')
  })

  it('never reports grounded from the inference flag alone', () => {
    // AI_COPILOT_INFERENCE_ENABLED is a second opener on top of AI_COPILOT_ENABLED;
    // with the master off the routes 404 and no inference happens at all.
    expect(
      resolveCopilotDisclosureMode({
        unavailable: false,
        copilotOpen: false,
        inferenceOpen: true,
      }),
    ).toBe('simulated')
  })

  it('lets an observed 404 override both flags', () => {
    // The flags are a cached read that can be up to a minute stale; the 404 is the
    // endpoint's own answer, so it wins.
    expect(
      resolveCopilotDisclosureMode({
        unavailable: true,
        copilotOpen: true,
        inferenceOpen: true,
      }),
    ).toBe('unavailable')
  })
})

describe('copilotDisclosure copy', () => {
  it('only the simulated mode denies that a model is involved', () => {
    expect(copilotDisclosure('simulated').banner?.lead).toMatch(/no AI model is involved/i)
    expect(copilotDisclosure('grounded').banner?.lead).not.toMatch(/no AI model/i)
    expect(copilotDisclosure('grounded').welcome).not.toMatch(/not connected to any AI model/i)
  })

  it('uses the PlantEx Assist product name in every mode', () => {
    expect(copilotDisclosure('unavailable').title).toBe('PlantEx Assist')
    expect(copilotDisclosure('simulated').title).toBe('PlantEx Assist (Demo)')
    expect(copilotDisclosure('grounded').title).toBe('PlantEx Assist')
    expect(copilotDisclosure('grounded').welcome).toMatch(/PlantEx Assist/)
  })

  it('leaves no user-visible "Copilot" wording in any mode', () => {
    // The technical spelling survives in the API path, the flags and the module
    // folder; none of it is allowed to reach a string a user reads.
    for (const mode of ['unavailable', 'simulated', 'grounded'] as const) {
      const { title, subtitle, welcome, inputPlaceholder, actionNotPerformed, banner } =
        copilotDisclosure(mode)
      const visible = [
        title,
        subtitle,
        welcome,
        inputPlaceholder,
        actionNotPerformed,
        banner?.lead ?? '',
        banner?.detail ?? '',
      ].join(' ')
      expect(visible).not.toMatch(/copilot/i)
    }
  })

  it('drops "(Demo)" from the title once answers are grounded', () => {
    expect(copilotDisclosure('simulated').title).toContain('(Demo)')
    expect(copilotDisclosure('grounded').title).not.toContain('Demo')
    expect(copilotDisclosure('unavailable').title).not.toContain('Demo')
  })

  it('states the grounded limits that make the claim honest', () => {
    const { banner, welcome } = copilotDisclosure('grounded')

    // Closed question set, citation-validated figures, no writes — each one a
    // property the server enforces rather than a hope about the model.
    expect(banner?.detail).toMatch(/fixed set of questions/i)
    expect(banner?.detail).toMatch(/must appear in those facts/i)
    expect(banner?.detail).toMatch(/never created, edited or deleted/i)
    expect(welcome).toMatch(/refuse/i)
  })

  it('never promises a write in any mode', () => {
    for (const mode of MODES) {
      expect(copilotDisclosure(mode).actionNotPerformed).toMatch(/not performed/i)
    }
  })

  it('leaves the unavailable state to its own alert rather than banner-stacking', () => {
    expect(copilotDisclosure('unavailable').banner).toBeNull()
    expect(copilotDisclosure('simulated').banner).not.toBeNull()
    expect(copilotDisclosure('grounded').banner).not.toBeNull()
  })

  it('gives the two banners distinct test ids and tones', () => {
    const simulated = copilotDisclosure('simulated').banner
    const grounded = copilotDisclosure('grounded').banner

    expect(simulated?.testId).not.toBe(grounded?.testId)
    expect(simulated?.tone).toBe('warning')
    expect(grounded?.tone).toBe('info')
  })
})
