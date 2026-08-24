import { describe, expect, it } from 'vitest'
import type { Investigation } from '../../api/client'
import {
  formatCapaActionsCount,
  getActionSourceLink,
  getCapaHandoffLabelKey,
  getCapaLink,
  getInvestigationDetailHref,
  getInvestigationSourceLink,
  parseComplianceRequirementId,
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
    expect(getCapaLink('near_miss', 3)).toBe('/actions?sourceType=near_miss&sourceId=3')
    expect(getCapaLink('rta', 42)).toBe('/actions?sourceType=rta&sourceId=42')
    expect(getCapaLink('complaint', 9)).toBe('/actions?sourceType=complaint&sourceId=9')
  })

  it('builds create deep-link with locked investigation parent + returnTo', () => {
    expect(
      getCapaLink('investigation', 7, {
        create: true,
        returnTo: '/investigations/7',
      }),
    ).toBe(
      '/actions?sourceType=investigation&sourceId=7&create=1&returnTo=%2Finvestigations%2F7',
    )
  })

  it('resolves create vs open CAPA hand-off mode', () => {
    expect(resolveCapaHandoffMode(0)).toBe('create')
    expect(resolveCapaHandoffMode(2)).toBe('open')
    expect(getCapaHandoffLabelKey('incident', 0)).toBe('investigations.handoff.create_action')
    expect(getCapaHandoffLabelKey('incident', 1)).toBe('incidents.detail.open_capa')
    expect(getCapaHandoffLabelKey('investigation', 3)).toBe('investigations.handoff.open_capa')
    expect(getCapaHandoffLabelKey('near_miss', 2)).toBe('near_misses.detail.open_capa')
    expect(getCapaHandoffLabelKey('complaint', 1)).toBe('complaints.detail.open_capa')
    expect(getCapaHandoffLabelKey('rta', 4)).toBe('rtas.detail.open_capa')
  })
})

describe('action source reverse deep-links', () => {
  it.each([
    ['incident', 11, '/incidents/11', 'actions.view_incident'],
    ['capa_incident', 11, '/incidents/11', 'actions.view_incident'],
    ['investigation', 21, '/investigations/21', 'actions.view_investigation'],
    ['audit_finding', 42, '/audits?view=findings&findingId=42', 'actions.view_finding'],
    ['near_miss', 3, '/near-misses/3', 'actions.view_near_miss'],
    ['rta', 42, '/rtas/42', 'actions.view_rta'],
    ['complaint', 9, '/complaints/9', 'actions.view_complaint'],
    ['capa_complaint', 9, '/complaints/9', 'actions.view_complaint'],
  ] as const)('maps %s/%s to %s', (sourceType, sourceId, href, labelKey) => {
    expect(getActionSourceLink(sourceType, sourceId)).toMatchObject({ href, labelKey })
  })

  it('returns null for unknown types or non-positive ids', () => {
    expect(getActionSourceLink('unknown_source', 9)).toBeNull()
    expect(getActionSourceLink('incident', 0)).toBeNull()
    expect(getActionSourceLink('incident', null)).toBeNull()
    expect(getActionSourceLink(undefined, 5)).toBeNull()
  })

  it('sends a compliance action to its obligation, not to its occurrence', () => {
    // source_id is the record (55); the page is the requirement (10).
    expect(
      getActionSourceLink('compliance_record', 55, 'compliance_requirement:10'),
    ).toMatchObject({
      href: '/compliance-schedule/10',
      labelKey: 'actions.view_compliance_requirement',
    })
  })

  it('offers no compliance link rather than a wrong one', () => {
    // /compliance-schedule/55 is a real route: guessing here would open a
    // different obligation, which is worse than not linking at all.
    expect(getActionSourceLink('compliance_record', 55)).toBeNull()
    expect(getActionSourceLink('compliance_record', 55, null)).toBeNull()
    expect(getActionSourceLink('compliance_record', 55, 'CRC-2026-0001')).toBeNull()
    expect(getActionSourceLink('compliance_record', 55, 'investigation:10')).toBeNull()
    expect(getActionSourceLink('compliance_record', 55, 'compliance_requirement:0')).toBeNull()
  })

  it('ignores a compliance reference on any other source type', () => {
    expect(getActionSourceLink('incident', 11, 'compliance_requirement:10')).toMatchObject({
      href: '/incidents/11',
    })
  })

  it('parses the obligation id out of the storage key', () => {
    expect(parseComplianceRequirementId('compliance_requirement:10')).toBe(10)
    expect(parseComplianceRequirementId('  compliance_requirement:7  ')).toBe(7)
    expect(parseComplianceRequirementId('compliance_requirement:abc')).toBeNull()
    expect(parseComplianceRequirementId(undefined)).toBeNull()
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
