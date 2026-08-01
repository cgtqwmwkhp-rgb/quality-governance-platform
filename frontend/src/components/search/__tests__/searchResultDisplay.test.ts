import { describe, expect, it } from 'vitest'

import {
  buildHighlightedSegments,
  collectHighlightTerms,
  DOCUMENT_CONTENT_MODULE,
  getSearchLocationMeta,
  isDocumentContentResult,
  isSnippetSuppressed,
  moduleDisplayLabel,
  MODULE_FILTER_OPTIONS,
  parsePageFromSearchPath,
  SNIPPET_SUPPRESSED,
  stripHeadlineMarkup,
} from '../searchResultDisplay'

describe('searchResultDisplay', () => {
  it('detects snippet_suppressed without inventing body text', () => {
    expect(isSnippetSuppressed([SNIPPET_SUPPRESSED])).toBe(true)
    expect(isSnippetSuppressed(['fire', SNIPPET_SUPPRESSED])).toBe(true)
    expect(isSnippetSuppressed(['fire'])).toBe(false)
    expect(isSnippetSuppressed([])).toBe(false)
    expect(isSnippetSuppressed(undefined)).toBe(false)
  })

  it('recognises document_content by type or module', () => {
    expect(isDocumentContentResult({ type: 'document_content', module: DOCUMENT_CONTENT_MODULE })).toBe(
      true,
    )
    expect(isDocumentContentResult({ type: 'document', module: 'Documents' })).toBe(false)
    expect(isDocumentContentResult({ module: DOCUMENT_CONTENT_MODULE })).toBe(true)
  })

  it('parses page from deep-link path and prefers explicit page_number', () => {
    expect(parsePageFromSearchPath('/documents/9?chunk=44&page=3')).toBe(3)
    expect(parsePageFromSearchPath('/documents/9')).toBeNull()
    expect(parsePageFromSearchPath(null)).toBeNull()

    expect(
      getSearchLocationMeta({
        heading: ' Fire safety ',
        path: '/documents/9?chunk=1&page=2',
      }),
    ).toEqual({ heading: 'Fire safety', page: 2 })

    expect(
      getSearchLocationMeta({
        heading: 'Intro',
        page_number: 5,
        path: '/documents/9?page=2',
      }),
    ).toEqual({ heading: 'Intro', page: 5 })
  })

  it('strips ts_headline markup and builds highlighted segments', () => {
    expect(stripHeadlineMarkup('use a <b>fire</b> extinguisher')).toBe('use a fire extinguisher')

    const terms = collectHighlightTerms(['fire'], 'keep a <b>extinguisher</b> nearby')
    expect(terms.map((t) => t.toLowerCase()).sort()).toEqual(['extinguisher', 'fire'])

    const segments = buildHighlightedSegments('use a <b>fire</b> extinguisher', ['fire'])
    expect(segments).toEqual([
      { text: 'use a ', highlighted: false },
      { text: 'fire', highlighted: true },
      { text: ' extinguisher', highlighted: false },
    ])
  })

  it('labels Document Content facet chip as Document body', () => {
    expect(moduleDisplayLabel(DOCUMENT_CONTENT_MODULE)).toBe('Document body')
    expect(MODULE_FILTER_OPTIONS.some((o) => o.value === DOCUMENT_CONTENT_MODULE)).toBe(true)
    expect(moduleDisplayLabel('Incidents')).toBe('Incidents')
  })
})
