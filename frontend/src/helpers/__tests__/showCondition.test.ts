import { describe, expect, it } from 'vitest'
import { fieldMatchesShowCondition } from '../showCondition'

describe('fieldMatchesShowCondition', () => {
  it('shows the field when there is no condition', () => {
    expect(fieldMatchesShowCondition(undefined, {})).toBe(true)
    expect(fieldMatchesShowCondition({}, { feedback_kind: 'complaint' })).toBe(true)
  })

  it('matches { field, equals } used by the compliment subject', () => {
    const condition = { field: 'feedback_kind', equals: 'compliment' }
    expect(fieldMatchesShowCondition(condition, { feedback_kind: 'compliment' })).toBe(true)
    expect(fieldMatchesShowCondition(condition, { feedback_kind: 'complaint' })).toBe(false)
    expect(fieldMatchesShowCondition(condition, {})).toBe(false)
  })

  it('matches a shorthand { feedback_kind: "compliment" } map', () => {
    expect(fieldMatchesShowCondition({ feedback_kind: 'compliment' }, { feedback_kind: 'compliment' })).toBe(
      true,
    )
    expect(fieldMatchesShowCondition({ feedback_kind: 'compliment' }, { feedback_kind: 'complaint' })).toBe(
      false,
    )
  })
})
