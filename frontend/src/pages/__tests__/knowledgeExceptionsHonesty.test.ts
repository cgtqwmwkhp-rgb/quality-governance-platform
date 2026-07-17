import { describe, expect, it } from 'vitest'
import {
  buildWhyDetail,
  dedupeKnowledgeExceptions,
  exceptionAllocationKey,
  formatSchemeLabel,
  isGenericRationale,
  normalizeSchemeKey,
  resolveClauseIdentity,
  type ExceptionLinkLike,
} from '../knowledgeExceptionsHonesty'

const baseLink = (overrides: Partial<ExceptionLinkLike>): ExceptionLinkLike => ({
  id: 1,
  entity_type: 'incident',
  entity_id: '7',
  clause_id: 'ISO9001:8.5',
  scheme: 'iso9001',
  status: 'proposed',
  rationale: 'Incident narrative cites missing work instruction for welding step 3.',
  title: 'Gap in documented procedure',
  notes: null,
  signal_type: 'gap',
  confidence: 0.72,
  linked_by: 'ai',
  ...overrides,
})

describe('knowledgeExceptionsHonesty — scheme + clause identity', () => {
  it('formats scheme labels clearly', () => {
    expect(formatSchemeLabel('iso9001')).toBe('ISO 9001')
    expect(formatSchemeLabel('iso27001')).toBe('ISO 27001')
    expect(formatSchemeLabel('uvdb')).toBe('UVDB Achilles')
    expect(formatSchemeLabel('planetmark')).toBe('Planet Mark')
  })

  it('normalizes scheme keys for stable keys', () => {
    expect(normalizeSchemeKey('ISO9001')).toBe('iso9001')
    expect(normalizeSchemeKey('Planet Mark')).toBe('planetmark')
  })

  it('resolves ISO clause title and section path from catalogue', () => {
    const identity = resolveClauseIdentity({
      scheme: 'iso9001',
      clause_id: 'ISO9001:8.5',
    })
    expect(identity.schemeLabel).toBe('ISO 9001')
    expect(identity.clauseNumber).toBe('8.5')
    expect(identity.clauseTitle).toMatch(/production/i)
    expect(identity.sectionPath).toMatch(/operation/i)
  })

  it('infers scheme from clause_id when scheme column missing', () => {
    const identity = resolveClauseIdentity({
      scheme: null,
      clause_id: '9001-7.5',
    })
    expect(identity.schemeKey).toBe('iso9001')
    expect(identity.clauseNumber).toBe('7.5')
  })
})

describe('knowledgeExceptionsHonesty — why detail', () => {
  it('flags generic rationales', () => {
    expect(isGenericRationale('possible gap')).toBe(true)
    expect(isGenericRationale('Incident cites missing WI for welding step 3.')).toBe(false)
  })

  it('builds specific why lines from rationale', () => {
    const detail = buildWhyDetail(baseLink({}))
    expect(detail.isGeneric).toBe(false)
    expect(detail.summary).toMatch(/welding/i)
    expect(detail.lines.some((l) => l.startsWith('Why:'))).toBe(true)
  })

  it('honestly labels generic AI rationale', () => {
    const detail = buildWhyDetail(
      baseLink({ rationale: 'possible gap', title: 'Gap', notes: null }),
    )
    expect(detail.isGeneric).toBe(true)
    expect(detail.lines.some((l) => l.includes('generic label'))).toBe(true)
  })
})

describe('knowledgeExceptionsHonesty — stable de-dupe', () => {
  it('uses entity × scheme × clause allocation key', () => {
    expect(
      exceptionAllocationKey({
        entity_type: 'incident',
        entity_id: '7',
        scheme: 'iso9001',
        clause_id: 'ISO9001:8.5',
      }),
    ).toBe('incident:7|iso9001|8.5')
    expect(
      exceptionAllocationKey({
        entity_type: 'incident',
        entity_id: '7',
        scheme: 'iso9001',
        clause_id: '9001-8.5',
      }),
    ).toBe('incident:7|iso9001|8.5')
  })

  it('collapses duplicate proposals to one actionable row', () => {
    const rows = dedupeKnowledgeExceptions([
      baseLink({ id: 10, confidence: 0.5 }),
      baseLink({ id: 11, confidence: 0.9, rationale: 'Stronger duplicate proposal.' }),
    ])
    expect(rows).toHaveLength(1)
    expect(rows[0].primary.id).toBe(11)
    expect(rows[0].allocationKind).toBe('duplicate_proposal')
    expect(rows[0].duplicates).toHaveLength(1)
  })

  it('surfaces already confirmed allocation instead of twin proposal', () => {
    const rows = dedupeKnowledgeExceptions([
      baseLink({ id: 20, status: 'proposed' }),
      baseLink({ id: 21, status: 'confirmed', rationale: 'Confirmed earlier.' }),
    ])
    expect(rows).toHaveLength(1)
    expect(rows[0].primary.status).toBe('confirmed')
    expect(rows[0].allocationKind).toBe('already_confirmed')
  })
})
