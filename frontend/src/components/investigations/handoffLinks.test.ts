import { describe, expect, it } from 'vitest'
import type { Investigation } from '../../api/client'
import { getCapaLink, getInvestigationSourceLink } from './handoffLinks'

const investigation = {
  id: 7,
  assigned_entity_id: 42,
} as Investigation

describe('investigation hand-off links', () => {
  it.each([
    ['reporting_incident', '/incidents/42', 'incident'],
    ['near_miss', '/near-misses/42', 'near miss'],
    ['road_traffic_collision', '/rtas/42', 'RTA'],
  ] as const)('maps %s sources to their detail route', (sourceType, href, label) => {
    expect(
      getInvestigationSourceLink({
        ...investigation,
        assigned_entity_type: sourceType,
      }),
    ).toEqual({ href, label })
  })

  it('builds encoded CAPA filters', () => {
    expect(getCapaLink('investigation', 7)).toBe(
      '/actions?sourceType=investigation&sourceId=7',
    )
  })
})
