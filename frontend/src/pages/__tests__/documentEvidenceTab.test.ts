import { describe, expect, it } from 'vitest'
import {
  PROPOSED_EVIDENCE_ANCHOR_ID,
  documentEvidenceHref,
  resolveDocumentDetailTab,
  shouldScrollToProposedEvidence,
} from '../documentEvidenceTab'

describe('resolveDocumentDetailTab', () => {
  it('opens Standards & Evidence when tab=evidence', () => {
    expect(resolveDocumentDetailTab('evidence')).toBe('evidence')
  })

  it('falls back to overview for missing or unknown tabs', () => {
    expect(resolveDocumentDetailTab(null)).toBe('overview')
    expect(resolveDocumentDetailTab('nope')).toBe('overview')
  })
})

describe('documentEvidenceHref', () => {
  it('deep-links to Standards & Evidence tab', () => {
    expect(documentEvidenceHref(42)).toBe('/documents/42?tab=evidence')
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
