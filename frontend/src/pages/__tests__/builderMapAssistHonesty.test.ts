import { describe, expect, it } from 'vitest'
import {
  MAP_W2_SCHEME_CHIPS,
  applyConfirmDecision,
  computeIsoClauseCoverage,
  hasIsoClauseText,
  mergeSuggestedLinks,
  primaryAcceptedIsoClause,
  schemeChipStatus,
} from '../builderMapAssistHonesty'
import type { MapW3StandardLink } from '../mapW3StaleRescoreHonesty'

const suggested = (overrides: Partial<MapW3StandardLink> = {}): MapW3StandardLink => ({
  id: 'sug-1',
  questionId: 'q-1',
  scheme: 'ISO',
  refId: '45001-8.2',
  label: 'Emergency',
  confidence: 0.9,
  status: 'suggested',
  sourceFingerprint: '',
  libraryVersion: 'builder-map-v1',
  ...overrides,
})

describe('builderMapAssistHonesty MAP-01..04', () => {
  it('exposes ISO / Planet Mark / UVDB scheme chips', () => {
    expect(MAP_W2_SCHEME_CHIPS).toEqual(['ISO', 'Planet Mark', 'UVDB'])
  })

  it('treats blank isoClause as uncovered', () => {
    expect(hasIsoClauseText(null)).toBe(false)
    expect(hasIsoClauseText('')).toBe(false)
    expect(hasIsoClauseText('  ')).toBe(false)
    expect(hasIsoClauseText('7.1.2')).toBe(true)
  })

  it('computes manual ISO + multi-scheme coverage with Assist Map live', () => {
    const stats = computeIsoClauseCoverage([
      {
        isoClause: '7.1.2',
        standardLinks: [suggested({ status: 'accepted', scheme: 'Planet Mark', refId: 'pm:scope1' })],
      },
      { isoClause: '' },
      { isoClause: '  ' },
      { isoClause: '8.1', standardLinks: [suggested({ id: 'a2', status: 'accepted', scheme: 'UVDB' })] },
    ])
    expect(stats.totalQuestions).toBe(4)
    expect(stats.withIsoClause).toBe(2)
    expect(stats.isoCoveragePercent).toBe(50)
    expect(stats.acceptedMultiSchemeLinks).toBe(2)
    expect(stats.questionsWithAcceptedLinks).toBe(2)
    expect(stats.multiSchemeCoveragePercent).toBe(50)
    expect(stats.assistMapLive).toBe(true)
    expect(stats.bySchemeAccepted['Planet Mark']).toBe(1)
    expect(stats.bySchemeAccepted.UVDB).toBe(1)
  })

  it('marks scheme chips accepted when multi-scheme links exist', () => {
    const stats = computeIsoClauseCoverage([
      {
        isoClause: '7.1.2',
        standardLinks: [
          suggested({ status: 'accepted' }),
          suggested({ id: 'pm', scheme: 'Planet Mark', refId: 'pm:x', status: 'accepted' }),
        ],
      },
    ])
    expect(schemeChipStatus('ISO', stats)).toBe('accepted')
    expect(schemeChipStatus('Planet Mark', stats)).toBe('accepted')
    expect(schemeChipStatus('UVDB', stats)).toBe('awaiting_assist')
  })

  it('falls back to manual_iso when only free-text ISO clause exists', () => {
    const stats = computeIsoClauseCoverage([{ isoClause: '7.1.2' }])
    expect(schemeChipStatus('ISO', stats)).toBe('manual_iso')
    expect(schemeChipStatus('Planet Mark', stats)).toBe('awaiting_assist')
  })

  it('applies confirm-loop accept / edit / reject decisions', () => {
    const links = [suggested()]
    expect(applyConfirmDecision(links, 'sug-1', 'accept')[0].status).toBe('accepted')
    expect(
      applyConfirmDecision(links, 'sug-1', 'edit', { refId: '45001-8.1', label: 'Edited' })[0],
    ).toMatchObject({ status: 'accepted', refId: '45001-8.1', label: 'Edited' })
    expect(applyConfirmDecision(links, 'sug-1', 'reject')[0].status).toBe('rejected')
  })

  it('merges suggestions without clobbering accepted or rejected links', () => {
    const existing = [
      suggested({ status: 'accepted' }),
      suggested({ id: 'r1', refId: 'uvdb:1', scheme: 'UVDB', status: 'rejected' }),
    ]
    const merged = mergeSuggestedLinks(existing, [
      suggested({ confidence: 0.5 }),
      suggested({ id: 'r1', refId: 'uvdb:1', scheme: 'UVDB', confidence: 0.99 }),
      suggested({ id: 'n1', refId: 'pm:scope2', scheme: 'Planet Mark' }),
    ])
    expect(merged.find((l) => l.refId === '45001-8.2')?.status).toBe('accepted')
    expect(merged.find((l) => l.refId === 'uvdb:1')?.status).toBe('rejected')
    expect(merged.find((l) => l.refId === 'pm:scope2')?.status).toBe('suggested')
  })

  it('returns primary accepted ISO clause for Advanced Settings sync', () => {
    expect(
      primaryAcceptedIsoClause([
        suggested({ scheme: 'UVDB', status: 'accepted', refId: 'uvdb:1' }),
        suggested({ status: 'accepted', refId: '9001-7.2' }),
      ]),
    ).toBe('9001-7.2')
  })

  it('returns zero coverage for empty question lists', () => {
    expect(computeIsoClauseCoverage([])).toMatchObject({
      totalQuestions: 0,
      withIsoClause: 0,
      isoCoveragePercent: 0,
      acceptedMultiSchemeLinks: 0,
      multiSchemeCoveragePercent: 0,
      assistMapLive: true,
    })
  })
})
