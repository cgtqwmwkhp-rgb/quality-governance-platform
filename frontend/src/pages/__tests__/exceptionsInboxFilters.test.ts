import { describe, expect, it } from 'vitest'
import {
  buildExceptionsInboxSearch,
  exceptionEntityHref,
  exceptionsStatusQueryParam,
  formatGateReasonLabel,
  parseExceptionsEntityTypeFilter,
  parseExceptionsGateReasonFilter,
  parseExceptionsSignalTypeFilter,
  parseExceptionsStatusFilter,
} from '../exceptionsInboxFilters'

describe('exceptions inbox filter parsers', () => {
  it('parses status with inbox default', () => {
    expect(parseExceptionsStatusFilter(null)).toBe('inbox')
    expect(parseExceptionsStatusFilter('proposed')).toBe('proposed')
    expect(parseExceptionsStatusFilter('needs_review')).toBe('needs_review')
    expect(parseExceptionsStatusFilter('bogus')).toBe('inbox')
  })

  it('parses entity_type and signal_type with all default', () => {
    expect(parseExceptionsEntityTypeFilter('complaint')).toBe('complaint')
    expect(parseExceptionsEntityTypeFilter('nope')).toBe('all')
    expect(parseExceptionsSignalTypeFilter('gap')).toBe('gap')
    expect(parseExceptionsSignalTypeFilter(undefined)).toBe('all')
  })

  it('parses gate_reason with all default', () => {
    expect(parseExceptionsGateReasonFilter('below_threshold')).toBe('below_threshold')
    expect(parseExceptionsGateReasonFilter('invented')).toBe('all')
    expect(formatGateReasonLabel('below_threshold')).toBe('Below 98% confidence')
    expect(formatGateReasonLabel(null)).toBe('Gate reason not logged')
  })
})

describe('exceptionsStatusQueryParam', () => {
  it('omits status for inbox (API default proposed+needs_review)', () => {
    expect(exceptionsStatusQueryParam('inbox')).toBeUndefined()
    expect(exceptionsStatusQueryParam('proposed')).toBe('proposed')
  })
})

describe('buildExceptionsInboxSearch', () => {
  it('syncs status + entity_type + signal_type into URL', () => {
    expect(
      buildExceptionsInboxSearch({
        status: 'proposed',
        entityType: 'incident',
        signalType: 'gap',
        gateReason: 'all',
      }),
    ).toBe('status=proposed&entity_type=incident&signal_type=gap')
  })

  it('omits default filters from URL', () => {
    expect(
      buildExceptionsInboxSearch({
        status: 'inbox',
        entityType: 'all',
        signalType: 'all',
        gateReason: 'all',
      }),
    ).toBe('')
  })

  it('syncs gate_reason into URL when set', () => {
    expect(
      buildExceptionsInboxSearch({
        status: 'inbox',
        entityType: 'document',
        signalType: 'all',
        gateReason: 'below_threshold',
      }),
    ).toBe('entity_type=document&gate_reason=below_threshold')
  })
})

describe('exceptionEntityHref', () => {
  it('deep-links cases to Standards tab and documents to evidence', () => {
    expect(exceptionEntityHref('document', '42')).toBe('/documents/42?tab=evidence')
    expect(exceptionEntityHref('incident', '7')).toBe('/incidents/7?tab=standards')
    expect(exceptionEntityHref('complaint', '3')).toBe('/complaints/3?tab=standards')
    expect(exceptionEntityHref('near_miss', '9')).toBe('/near-misses/9?tab=standards')
    expect(exceptionEntityHref('rta', '5')).toBe('/rtas/5?tab=standards')
  })
})
