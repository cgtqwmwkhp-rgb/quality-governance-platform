import { describe, expect, it } from 'vitest'
import { REGISTER_CATALOGUE } from '../../../data/registerCatalogue'
import {
  ACTIONS_CLIENT_ONLY_PARAMS,
  ACTIONS_SERVER_FILTERABLE_PARAMS,
} from '../actionsServerFilterableParams'

describe('actions SERVER_FILTERABLE_PARAMS', () => {
  it('does not claim register as a SQL filter', () => {
    expect(ACTIONS_SERVER_FILTERABLE_PARAMS).toContain('source_type')
    for (const name of ACTIONS_CLIENT_ONLY_PARAMS) {
      expect(ACTIONS_SERVER_FILTERABLE_PARAMS).not.toContain(name)
    }
  })

  it('has no modern slavery parameter to filter the tracker by', () => {
    for (const name of ACTIONS_SERVER_FILTERABLE_PARAMS) {
      expect(name).not.toMatch(/slavery|register|pel/i)
    }
  })

  it('keeps every /actions captionQuery to keys the caption banner can honour', () => {
    // Actions.tsx passes only `register` to RegisterCaptionBanner. A `type=` or
    // `statutory=` added here would print nothing and filter nothing.
    const captioned = REGISTER_CATALOGUE.filter((e) => e.to === '/actions')
    expect(captioned.length).toBeGreaterThan(0)
    for (const entry of captioned) {
      expect([...new URLSearchParams(entry.captionQuery!).keys()]).toEqual(['register'])
    }
  })
})
