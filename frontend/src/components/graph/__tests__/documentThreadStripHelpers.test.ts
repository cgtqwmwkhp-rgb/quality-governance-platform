import { describe, expect, it } from 'vitest'
import type { DocumentThreadHop, DocumentThreadResponse } from '../../../api/documentGraphClient'
import {
  buildThreadStripItems,
  hopDisplayTitle,
  shouldFetchDocumentThread,
  shouldShowDocumentThreadStrip,
  threadStripHasNeighbors,
} from '../documentThreadStripHelpers'

function hop(overrides: Partial<DocumentThreadHop> & Pick<DocumentThreadHop, 'document_id' | 'edge_id'>): DocumentThreadHop {
  return {
    depth: 1,
    direction: 'parent',
    href: `/documents/${overrides.document_id}`,
    origin: 'graph',
    status: 'confirmed',
    title: null,
    reference: null,
    ...overrides,
  }
}

describe('documentThreadStripHelpers', () => {
  it('hides the strip when the ambient flag is off', () => {
    expect(shouldShowDocumentThreadStrip(false)).toBe(false)
    expect(shouldShowDocumentThreadStrip(true)).toBe(true)
  })

  it('fetches only when master Doc Graph and ambient flags are both on', () => {
    expect(shouldFetchDocumentThread(false, true)).toBe(false)
    expect(shouldFetchDocumentThread(true, false)).toBe(false)
    expect(shouldFetchDocumentThread(true, true)).toBe(true)
  })

  it('prefers title, then reference, then document id for hop labels', () => {
    expect(hopDisplayTitle(hop({ document_id: 1, edge_id: 1, title: 'Policy' }))).toBe('Policy')
    expect(
      hopDisplayTitle(hop({ document_id: 2, edge_id: 2, title: null, reference: 'POL-1' })),
    ).toBe('POL-1')
    expect(hopDisplayTitle(hop({ document_id: 3, edge_id: 3 }))).toBe('Document #3')
  })

  it('orders ancestors root-first, then current, then descendants by depth', () => {
    const thread: DocumentThreadResponse = {
      document_id: 10,
      max_depth: 4,
      ancestors: [
        hop({
          document_id: 2,
          edge_id: 20,
          depth: 1,
          title: 'Procedure',
          reference: 'PR-2',
        }),
        hop({
          document_id: 1,
          edge_id: 10,
          depth: 2,
          title: 'Policy',
          reference: 'POL-1',
        }),
      ],
      descendants: [
        hop({
          document_id: 30,
          edge_id: 30,
          depth: 2,
          direction: 'child',
          title: 'Work instruction',
        }),
        hop({
          document_id: 20,
          edge_id: 21,
          depth: 1,
          direction: 'child',
          title: 'SOP',
        }),
      ],
    }

    const items = buildThreadStripItems(thread, {
      documentId: 10,
      title: 'Incident Reporting SOP',
      reference: 'SOP-10',
    })

    expect(items.map((item) => item.documentId)).toEqual([1, 2, 10, 20, 30])
    expect(items[0].kind).toBe('hop')
    expect(items[0].href).toBe('/documents/1')
    expect(items[2].kind).toBe('current')
    expect(items[2].reference).toBe('SOP-10')
    expect(threadStripHasNeighbors(items)).toBe(true)
  })

  it('treats a lone current document as empty neighbors', () => {
    const items = buildThreadStripItems(null, {
      documentId: 10,
      title: 'Lone',
    })
    expect(items).toHaveLength(1)
    expect(threadStripHasNeighbors(items)).toBe(false)
  })
})
