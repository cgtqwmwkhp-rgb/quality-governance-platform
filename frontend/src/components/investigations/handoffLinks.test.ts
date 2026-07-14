import { describe, expect, it } from 'vitest'
import type { Investigation } from '../../api/client'
import {
  formatCapaActionsCount,
  getActionSourceLink,
  getCapaHandoffLabelKey,
  getCapaLink,
  getInvestigationDetailHref,
  getInvestigationSourceLink,
  resolveCapaHandoffMode,
} from './handoffLinks'

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
    expect(getCapaLink('incident', 11)).toBe('/actions?sourceType=incident&sourceId=11')
  })

  it('resolves create vs open CAPA hand-off mode', () => {
    expect(resolveCapaHandoffMode(0)).toBe('create')
    expect(resolveCapaHandoffMode(2)).toBe('open')
    expect(getCapaHandoffLabelKey('incident', 0)).toBe('investigations.handoff.create_action')
    expect(getCapaHandoffLabelKey('incident', 1)).toBe('incidents.detail.open_capa')
    expect(getCapaHandoffLabelKey('investigation', 3)).toBe('investigations.handoff.open_capa')
  })
})

describe('action source reverse deep-links', () => {
  it.each([
    ['incident', 11, '/incidents/11', 'actions.view_incident'],
    ['capa_incident', 11, '/incidents/11', 'actions.view_incident'],
    ['investigation', 21, '/investigations/21', 'actions.view_investigation'],
    ['audit_finding', 42, '/audits?view=findings&findingId=42', 'actions.view_finding'],
  ] as const)('maps %s/%s to %s', (sourceType, sourceId, href, labelKey) => {
    expect(getActionSourceLink(sourceType, sourceId)).toMatchObject({ href, labelKey })
  })

  it('returns null for unknown types or non-positive ids', () => {
    expect(getActionSourceLink('complaint', 9)).toBeNull()
    expect(getActionSourceLink('incident', 0)).toBeNull()
    expect(getActionSourceLink('incident', null)).toBeNull()
    expect(getActionSourceLink(undefined, 5)).toBeNull()
  })

  it('formats CAPA counts with residual honesty', () => {
    expect(formatCapaActionsCount({ loading: true, count: 0 })).toBe('…')
    expect(formatCapaActionsCount({ unavailable: true, count: 0 })).toBe('—')
    expect(formatCapaActionsCount({ count: 3 })).toBe('3')
  })

  it('builds investigation detail deep links', () => {
    expect(getInvestigationDetailHref(21)).toBe('/investigations/21')
  })
})
