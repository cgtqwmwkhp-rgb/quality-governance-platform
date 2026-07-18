import { describe, expect, it } from 'vitest'
import {
  buildDocumentDownstreamView,
  buildDocumentsExceptionsHref,
  resolveDocumentDownstreamPhase,
} from '../documentsDownstreamHelpers'

describe('documentsDownstreamHelpers', () => {
  it('maps processing status to indexing honesty without exceptions link', () => {
    const view = buildDocumentDownstreamView({ id: 3, status: 'processing' })
    expect(view.phase).toBe('processing')
    expect(view.showExceptionsLink).toBe(false)
    expect(view.titleKey).toBe('documents.downstream.processing.title')
  })

  it('maps indexed status to AI Exceptions handoff', () => {
    const view = buildDocumentDownstreamView({
      id: 11,
      status: 'indexed',
      indexed_at: '2026-03-22T10:00:00Z',
    })
    expect(view.phase).toBe('indexed')
    expect(view.showExceptionsLink).toBe(true)
    expect(view.showDocumentControlNote).toBe(true)
  })

  it('treats published docs with indexed_at as indexed (publish must not hide readiness)', () => {
    const view = buildDocumentDownstreamView({
      id: 22,
      status: 'published',
      indexed_at: '2026-07-18T12:00:00Z',
      chunk_count: 12,
    })
    expect(view.phase).toBe('indexed')
    expect(view.showExceptionsLink).toBe(true)
  })

  it('treats published docs with chunks but no indexed_at as content-ready', () => {
    expect(resolveDocumentDownstreamPhase('published', null, 4)).toBe('indexed')
  })

  it('treats published docs with AI summary as content-ready for golden thread', () => {
    const view = buildDocumentDownstreamView({
      id: 33,
      status: 'published',
      ai_summary: 'This policy sets EDI obligations for Plantexpand Ltd.',
    })
    expect(view.phase).toBe('indexed')
  })

  it('builds closed-loop AI Exceptions href for a library document', () => {
    expect(buildDocumentsExceptionsHref(11)).toContain('/knowledge-exceptions?')
    expect(buildDocumentsExceptionsHref(11)).toContain('entity_type=document')
    expect(buildDocumentsExceptionsHref(11)).toContain('returnTo=%2Fdocuments%2F11%3Ftab%3Devidence')
  })

  it('classifies failed uploads separately from processing', () => {
    expect(resolveDocumentDownstreamPhase('failed')).toBe('failed')
  })
})
