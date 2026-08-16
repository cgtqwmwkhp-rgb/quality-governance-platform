import { describe, expect, it } from 'vitest'
import {
  instrumentCtaKey,
  instrumentRunHref,
  instrumentTag,
  parseInstrument,
  parseInstrumentQuery,
  parseInstrumentTag,
  templatesMatchingInstrument,
  upsertInstrumentTag,
} from '../auditInstrument'

describe('auditInstrument', () => {
  it('defaults untagged templates to audit', () => {
    expect(parseInstrument(undefined)).toBe('audit')
    expect(parseInstrument(null)).toBe('audit')
    expect(parseInstrument([])).toBe('audit')
    expect(parseInstrument(['builder_brief:abc'])).toBe('audit')
    expect(parseInstrumentTag([])).toBeNull()
  })

  it('filters picker lists by purpose and treats untagged as audit', () => {
    const items = [
      { id: 1, tags: ['instrument:audit'] },
      { id: 2, tags: ['instrument:skills'] },
      { id: 3, tags: ['instrument:induction'] },
      { id: 4, tags: [] },
    ]
    expect(templatesMatchingInstrument(items, 'audit').map((item) => item.id)).toEqual([1, 4])
    expect(templatesMatchingInstrument(items, 'skills').map((item) => item.id)).toEqual([2])
    expect(templatesMatchingInstrument(items, 'induction').map((item) => item.id)).toEqual([3])
  })

  it('parses instrument tags without overloading audit_type', () => {
    expect(parseInstrument(['instrument:audit'])).toBe('audit')
    expect(parseInstrument(['instrument:skills'])).toBe('skills')
    expect(parseInstrument(['instrument:induction'])).toBe('induction')
  })

  it('parses URL instrument only when it is a known purpose', () => {
    expect(parseInstrumentQuery('audit')).toBe('audit')
    expect(parseInstrumentQuery('skills')).toBe('skills')
    expect(parseInstrumentQuery('induction')).toBe('induction')
    expect(parseInstrumentQuery('inspection')).toBeNull()
    expect(parseInstrumentQuery('')).toBeNull()
    expect(parseInstrumentQuery(null)).toBeNull()
  })

  it('upserts the instrument tag and preserves builder_brief / source_case tags', () => {
    const stamped = upsertInstrumentTag(
      ['builder_brief:brief-1', 'source_case:complaint:9'],
      'skills',
    )
    expect(stamped).toEqual([
      'builder_brief:brief-1',
      'source_case:complaint:9',
      'instrument:skills',
    ])
    expect(upsertInstrumentTag(['instrument:audit', 'builder_brief:x'], 'induction')).toEqual([
      'builder_brief:x',
      'instrument:induction',
    ])
    expect(upsertInstrumentTag([], 'audit')).toEqual([instrumentTag('audit')])
  })

  it('routes the post-publish CTA by purpose', () => {
    expect(instrumentRunHref('audit', 12)).toBe('/audits?templateId=12')
    expect(instrumentRunHref('skills', 12)).toBe('/workforce/assessments/new?templateId=12')
    expect(instrumentRunHref('induction', 12)).toBe('/workforce/training/new?templateId=12')
    expect(instrumentCtaKey('audit')).toBe('audit_builder.cta.schedule_audit')
    expect(instrumentCtaKey('skills')).toBe('audit_builder.cta.start_skills')
    expect(instrumentCtaKey('induction')).toBe('audit_builder.cta.start_induction')
  })
})
