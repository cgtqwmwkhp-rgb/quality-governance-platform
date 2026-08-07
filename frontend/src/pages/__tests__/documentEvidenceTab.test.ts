import { describe, expect, it } from 'vitest'
import {
  PROPOSED_EVIDENCE_ANCHOR_ID,
  documentEvidenceHref,
  documentRelationshipsHref,
  resolveDocumentDetailTab,
  shouldScrollToProposedEvidence,
} from '../documentEvidenceTab'

describe('resolveDocumentDetailTab', () => {
  it('opens Standards & Evidence when tab=evidence', () => {
    expect(resolveDocumentDetailTab('evidence')).toBe('evidence')
  })

  it('opens Campaign results when tab=campaign-results', () => {
    expect(resolveDocumentDetailTab('campaign-results')).toBe('campaign-results')
  })

  it('falls back to overview for missing or unknown tabs', () => {
    expect(resolveDocumentDetailTab(null)).toBe('overview')
    expect(resolveDocumentDetailTab('nope')).toBe('overview')
  })

  it('opens Relationships when Doc Graph is open', () => {
    expect(resolveDocumentDetailTab('relationships', { documentGraphEnabled: true })).toBe(
      'relationships',
    )
  })

  it('falls back to overview when Doc Graph is closed, so the deep link cannot land on a missing tab', () => {
    expect(resolveDocumentDetailTab('relationships', { documentGraphEnabled: false })).toBe(
      'overview',
    )
  })
})

describe('documentEvidenceHref', () => {
  it('deep-links to Standards & Evidence tab', () => {
    expect(documentEvidenceHref(42)).toBe('/documents/42?tab=evidence')
  })
})

describe('documentRelationshipsHref', () => {
  it('deep-links to the Relationships tab', () => {
    expect(documentRelationshipsHref(42)).toBe('/documents/42?tab=relationships')
  })
})

describe('shouldScrollToProposedEvidence', () => {
  it('scrolls on evidence tab by default', () => {
    expect(shouldScrollToProposedEvidence('evidence')).toBe(true)
    expect(shouldScrollToProposedEvidence('evidence', '')).toBe(true)
    expect(shouldScrollToProposedEvidence('evidence', `#${PROPOSED_EVIDENCE_ANCHOR_ID}`)).toBe(
      true,
    )
  })

  it('does not scroll on other tabs', () => {
    expect(shouldScrollToProposedEvidence('overview')).toBe(false)
    expect(shouldScrollToProposedEvidence(null)).toBe(false)
  })
})
