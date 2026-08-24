import { describe, expect, it } from 'vitest'
import {
  obligationMentionsClause,
  scheduleProgrammeHref,
} from '../scheduleProgrammeContext'

describe('scheduleProgrammeHref', () => {
  it('lands on the Schedule SoR with clause and framework context', () => {
    expect(scheduleProgrammeHref('9001', '6.1.3')).toBe(
      '/compliance-schedule?clause=6.1.3&framework=9001',
    )
  })

  it('omits empty params rather than inventing a filter', () => {
    expect(scheduleProgrammeHref(null, '  ')).toBe('/compliance-schedule')
    expect(scheduleProgrammeHref('14001', undefined)).toBe(
      '/compliance-schedule?framework=14001',
    )
  })
})

describe('obligationMentionsClause', () => {
  it('matches clause tokens in title or regulatory basis', () => {
    expect(
      obligationMentionsClause(
        { title: 'Legal register (ISO 9001 6.1.3)', regulatory_basis: 'ISO 9001' },
        '6.1.3',
      ),
    ).toBe(true)
    expect(
      obligationMentionsClause({ title: 'Fire risk assessment', regulatory_basis: 'RRFSO' }, '6.1.3'),
    ).toBe(false)
  })

  it('does not treat a blank clause as a match against the whole register', () => {
    expect(obligationMentionsClause({ title: 'Anything' }, '  ')).toBe(false)
  })
})
