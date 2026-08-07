import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { DocumentRelationshipChips } from '../DocumentRelationshipChips'
import { summariseDocumentRelationships } from '../documentRelationshipHelpers'
import type { DocumentEdge } from '../../api/documentGraphClient'

function edge(overrides: Partial<DocumentEdge> & { id: number }): DocumentEdge {
  return {
    tenant_id: 1,
    src_document_id: 10,
    dst_document_id: 20,
    edge_type: 'implements',
    is_primary_parent: false,
    status: 'confirmed',
    created_method: 'manual',
    created_at: '2026-08-01T10:00:00Z',
    updated_at: '2026-08-01T10:00:00Z',
    ...overrides,
  }
}

function renderChips(edges: DocumentEdge[], evidenceCount = 0) {
  return render(
    <MemoryRouter>
      <DocumentRelationshipChips
        documentId={10}
        summary={summariseDocumentRelationships(10, edges)}
        evidenceCount={evidenceCount}
      />
    </MemoryRouter>,
  )
}

describe('DocumentRelationshipChips', () => {
  it('always shows the confirmed count and deep-links to the Relationships tab', () => {
    renderChips([edge({ id: 1 })], 3)
    expect(screen.getByTestId('document-relationship-chip-total')).toHaveAttribute(
      'href',
      '/documents/10?tab=relationships',
    )
    expect(screen.getByTestId('document-relationship-chip-total')).toHaveTextContent(
      '1 relationship',
    )
    expect(screen.getByTestId('document-relationship-chip-evidence')).toHaveTextContent(
      '3 clause evidence',
    )
  })

  it('stays quiet when there is nothing pending and nothing in conflict', () => {
    renderChips([edge({ id: 1 })])
    expect(screen.queryByTestId('document-relationship-chip-pending')).not.toBeInTheDocument()
    expect(screen.queryByTestId('document-relationship-chip-conflicts')).not.toBeInTheDocument()
    expect(screen.getByTestId('document-relationship-chip-total')).toHaveTextContent(
      '1 relationship',
    )
  })

  it('raises pending and conflict counts when they exist', () => {
    renderChips([
      edge({ id: 1, status: 'proposed' }),
      edge({ id: 2, dst_document_id: 30, edge_type: 'conflicts_with' }),
    ])
    expect(screen.getByTestId('document-relationship-chip-pending')).toHaveTextContent(
      '1 to confirm',
    )
    expect(screen.getByTestId('document-relationship-chip-conflicts')).toHaveTextContent(
      '1 conflict',
    )
  })

  it('pluralises zero relationships correctly', () => {
    renderChips([])
    expect(screen.getByTestId('document-relationship-chip-total')).toHaveTextContent(
      '0 relationships',
    )
  })
})
