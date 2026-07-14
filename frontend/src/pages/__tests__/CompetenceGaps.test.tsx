import { describe, expect, it } from 'vitest'
import { competenceGapActionHref } from '../CompetenceGaps'

describe('competenceGapActionHref', () => {
  it('deep-links to workforce competence gaps inbox with id', () => {
    expect(competenceGapActionHref(42)).toBe('/workforce/competence-gaps?id=42')
  })
})
