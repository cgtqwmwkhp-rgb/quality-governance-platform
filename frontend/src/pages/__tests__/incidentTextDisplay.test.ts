import { describe, expect, it } from 'vitest'
import { displayIncidentText } from '../incidentTextDisplay'

describe('displayIncidentText', () => {
  it('decodes stored HTML entities for display', () => {
    expect(displayIncidentText('Tools &amp; equipment')).toBe('Tools & equipment')
  })

  it('returns empty string for nullish values', () => {
    expect(displayIncidentText(null)).toBe('')
    expect(displayIncidentText(undefined)).toBe('')
  })
})
