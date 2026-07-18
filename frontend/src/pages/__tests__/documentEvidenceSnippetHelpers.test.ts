import { describe, expect, it } from 'vitest'
import type { KnowledgeEvidenceLink } from '../../api/knowledgeBankClient'
import { parseEvidenceQuote } from '../documentEvidenceSnippetHelpers'

function link(overrides: Partial<KnowledgeEvidenceLink> = {}): KnowledgeEvidenceLink {
  return {
    id: 1,
    entity_type: 'document',
    entity_id: '42',
    clause_id: '9001-7.2',
    linked_by: 'ai',
    confidence: 0.8,
    status: 'proposed',
    scheme: 'iso9001',
    auto_applied: false,
    rationale: null,
    title: 'Competence',
    notes: null,
    created_at: '2026-01-01T00:00:00Z',
    created_by_email: null,
    ...overrides,
  }
}

describe('parseEvidenceQuote', () => {
  it('prefers dedicated evidence_snippet and source_page fields', () => {
    const parsed = parseEvidenceQuote(
      link({
        evidence_snippet: 'All staff receive induction training.',
        source_page: 4,
        rationale: 'ignored when snippet present',
      }),
    )
    expect(parsed.snippet).toBe('All staff receive induction training.')
    expect(parsed.page).toBe(4)
  })

  it('uses rationale text as snippet for ISO-style quotes', () => {
    const parsed = parseEvidenceQuote(
      link({ rationale: 'All personnel are trained before starting work.' }),
    )
    expect(parsed.snippet).toBe('All personnel are trained before starting work.')
  })

  it('extracts page numbers from rationale', () => {
    const parsed = parseEvidenceQuote(
      link({ rationale: 'See competence records on page 12 for auditors.' }),
    )
    expect(parsed.page).toBe(12)
  })

  it('does not treat generic mapping rationale as a document quote', () => {
    const parsed = parseEvidenceQuote(
      link({ rationale: 'UVDB keyword match (training, competence)' }),
    )
    expect(parsed.snippet).toBeNull()
    expect(parsed.rationaleWithoutQuote).toContain('UVDB keyword match')
  })
})
