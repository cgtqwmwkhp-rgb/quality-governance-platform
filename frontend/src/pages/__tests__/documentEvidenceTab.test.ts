import { describe, expect, it } from 'vitest'
import {
  DOCUMENT_DETAIL_LAYERS,
  LEGACY_TAB_ALIASES,
  PROPOSED_EVIDENCE_ANCHOR_ID,
  documentDetailSectionDomId,
  documentEvidenceHref,
  documentLayerHref,
  documentRelationshipsHref,
  resolveDocumentDetailSection,
  resolveDocumentDetailTab,
  shouldScrollToProposedEvidence,
} from '../documentEvidenceTab'

describe('DOCUMENT_DETAIL_LAYERS', () => {
  it('locks the six spine layers in conveyor order', () => {
    expect(DOCUMENT_DETAIL_LAYERS).toEqual([
      'control',
      'coverage',
      'related',
      'used-by',
      'history',
      'assurance',
      'preview',
    ])
  })
})

describe('resolveDocumentDetailTab', () => {
  it('accepts canonical layer ids', () => {
    for (const layer of DOCUMENT_DETAIL_LAYERS) {
      expect(resolveDocumentDetailTab(layer)).toBe(layer)
    }
  })

  it('maps every legacy tab alias onto a layer', () => {
    expect(resolveDocumentDetailTab('evidence')).toBe('coverage')
    expect(resolveDocumentDetailTab('campaign-results')).toBe('used-by')
    expect(resolveDocumentDetailTab('overview')).toBe('control')
    expect(resolveDocumentDetailTab('relationships')).toBe('related')
    expect(resolveDocumentDetailTab('versions')).toBe('history')
    expect(resolveDocumentDetailTab('quiz')).toBe('assurance')
    expect(resolveDocumentDetailTab('qa')).toBe('assurance')
    expect(resolveDocumentDetailTab('watch')).toBe('assurance')
  })

  it('falls back to control for missing or unknown tabs', () => {
    expect(resolveDocumentDetailTab(null)).toBe('control')
    expect(resolveDocumentDetailTab('nope')).toBe('control')
  })

  it('keeps Related resolvable when Doc Graph is closed (no redirect)', () => {
    expect(resolveDocumentDetailTab('relationships', { documentGraphEnabled: false })).toBe(
      'related',
    )
    expect(resolveDocumentDetailTab('related', { documentGraphEnabled: false })).toBe('related')
  })

  it('covers the full LEGACY_TAB_ALIASES table', () => {
    for (const [legacy, mapped] of Object.entries(LEGACY_TAB_ALIASES)) {
      expect(resolveDocumentDetailTab(legacy)).toBe(mapped.layer)
    }
  })
})

describe('resolveDocumentDetailSection', () => {
  it('returns section anchors for legacy assurance / used-by deep links', () => {
    expect(resolveDocumentDetailSection('quiz')).toBe('quiz')
    expect(resolveDocumentDetailSection('qa')).toBe('qa')
    expect(resolveDocumentDetailSection('watch')).toBe('watch')
    expect(resolveDocumentDetailSection('campaign-results')).toBe('campaign-results')
  })

  it('returns null for canonical layers and unknown values', () => {
    expect(resolveDocumentDetailSection('control')).toBeNull()
    expect(resolveDocumentDetailSection('coverage')).toBeNull()
    expect(resolveDocumentDetailSection(null)).toBeNull()
    expect(resolveDocumentDetailSection('nope')).toBeNull()
  })

  it('builds stable section DOM ids', () => {
    expect(documentDetailSectionDomId('qa')).toBe('document-detail-section-qa')
  })
})

describe('documentEvidenceHref', () => {
  it('keeps emitting the legacy Standards & Evidence deep link', () => {
    expect(documentEvidenceHref(42)).toBe('/documents/42?tab=evidence')
  })
})

describe('documentRelationshipsHref', () => {
  it('keeps emitting the legacy Relationships deep link', () => {
    expect(documentRelationshipsHref(42)).toBe('/documents/42?tab=relationships')
  })
})

describe('documentLayerHref', () => {
  it('emits canonical layer links with optional section hash', () => {
    expect(documentLayerHref(7, 'used-by')).toBe('/documents/7?tab=used-by')
    expect(documentLayerHref(7, 'assurance', 'qa')).toBe(
      '/documents/7?tab=assurance#document-detail-section-qa',
    )
  })
})

describe('shouldScrollToProposedEvidence', () => {
  it('scrolls on coverage (and legacy evidence) by default', () => {
    expect(shouldScrollToProposedEvidence('evidence')).toBe(true)
    expect(shouldScrollToProposedEvidence('coverage')).toBe(true)
    expect(shouldScrollToProposedEvidence('evidence', '')).toBe(true)
    expect(shouldScrollToProposedEvidence('evidence', `#${PROPOSED_EVIDENCE_ANCHOR_ID}`)).toBe(
      true,
    )
  })

  it('does not scroll on other tabs', () => {
    expect(shouldScrollToProposedEvidence('overview')).toBe(false)
    expect(shouldScrollToProposedEvidence('control')).toBe(false)
    expect(shouldScrollToProposedEvidence(null)).toBe(false)
  })
})
