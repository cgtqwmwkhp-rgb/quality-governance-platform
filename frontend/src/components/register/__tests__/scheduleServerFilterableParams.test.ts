import { describe, expect, it } from 'vitest'
import {
  parseStatutoryParam,
  SCHEDULE_CLIENT_ONLY_PARAMS,
  SCHEDULE_SERVER_FILTERABLE_PARAMS,
} from '../scheduleServerFilterableParams'

describe('schedule SERVER_FILTERABLE_PARAMS', () => {
  it('treats statutory as SQL and clause/register as caption-only', () => {
    expect(SCHEDULE_SERVER_FILTERABLE_PARAMS).toContain('statutory')
    expect(SCHEDULE_SERVER_FILTERABLE_PARAMS).not.toContain('clause')
    expect(SCHEDULE_SERVER_FILTERABLE_PARAMS).not.toContain('framework')
    expect(SCHEDULE_SERVER_FILTERABLE_PARAMS).not.toContain('register')
    for (const name of SCHEDULE_CLIENT_ONLY_PARAMS) {
      expect(SCHEDULE_SERVER_FILTERABLE_PARAMS).not.toContain(name)
    }
  })

  it('parses statutory query values without guessing', () => {
    expect(parseStatutoryParam('true')).toBe(true)
    expect(parseStatutoryParam('false')).toBe(false)
    expect(parseStatutoryParam('maybe')).toBeUndefined()
    expect(parseStatutoryParam(null)).toBeUndefined()
  })
})
