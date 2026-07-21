import { describe, expect, it } from 'vitest'
import { mergeLookupSelectOptions } from '../lookupSelectOptions'

describe('mergeLookupSelectOptions', () => {
  const defaults = [
    { value: 'other', label: 'Other' },
    { value: 'service', label: 'Service' },
  ]

  it('returns defaults when lookup is empty', () => {
    expect(mergeLookupSelectOptions(defaults, [])).toEqual(defaults)
  })

  it('overrides labels for known codes and ignores unknown lookup codes', () => {
    expect(
      mergeLookupSelectOptions(defaults, [
        {
          id: 1,
          category: 'complaint_types',
          code: 'service',
          label: 'Service quality',
          is_active: true,
          display_order: 0,
        },
        {
          id: 2,
          category: 'complaint_types',
          code: 'defra_topic',
          label: 'DEFRA topic',
          is_active: true,
          display_order: 1,
        },
      ]),
    ).toEqual([
      { value: 'other', label: 'Other' },
      { value: 'service', label: 'Service quality' },
    ])
  })
})
