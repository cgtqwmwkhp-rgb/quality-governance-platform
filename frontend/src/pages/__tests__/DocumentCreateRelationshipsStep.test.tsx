import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { DocumentCreateRelationshipsStep } from '../DocumentCreateRelationshipsStep'

const apiGet = vi.fn()
const createEdge = vi.fn()

vi.mock('../../api/client', () => ({
  default: { get: (...args: unknown[]) => apiGet(...args) },
  documentGraphApi: {
    createEdge: (...args: unknown[]) => createEdge(...args),
  },
  getApiErrorMessage: (err: unknown) => (err as Error)?.message ?? 'error',
}))

vi.mock('../../contexts/ToastContext', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}))

describe('DocumentCreateRelationshipsStep', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    apiGet.mockResolvedValue({
      data: {
        items: [{ id: 20, title: 'Incident Management Policy', reference_number: 'DOC-20' }],
      },
    })
    createEdge.mockResolvedValue({
      data: {
        id: 7,
        tenant_id: 1,
        src_document_id: 99,
        dst_document_id: 20,
        edge_type: 'implements',
        is_primary_parent: true,
        status: 'confirmed',
        created_method: 'manual',
        created_at: '2026-08-07T12:00:00Z',
        updated_at: '2026-08-07T12:00:00Z',
      },
    })
  })

  it('records an implements edge via createEdge and lists it', async () => {
    const onDone = vi.fn()
    render(
      <MemoryRouter>
        <DocumentCreateRelationshipsStep
          documentId={99}
          documentTitle="Incident Reporting SOP"
          onDone={onDone}
        />
      </MemoryRouter>,
    )

    expect(screen.getByTestId('documents-create-relationships-step')).toBeInTheDocument()
    expect(screen.getByTestId('documents-create-rel-type')).toHaveValue('implements')
    // references is intentionally not offered at create time
    expect(screen.getByTestId('documents-create-rel-type').textContent).not.toMatch(/References/)

    fireEvent.change(screen.getByTestId('documents-create-rel-search'), {
      target: { value: 'Incident' },
    })
    expect(await screen.findByTestId('documents-create-rel-result-20')).toBeInTheDocument()
    fireEvent.click(screen.getByTestId('documents-create-rel-result-20'))
    fireEvent.click(screen.getByTestId('documents-create-rel-submit'))

    await waitFor(() => {
      expect(createEdge).toHaveBeenCalledWith({
        src_document_id: 99,
        dst_document_id: 20,
        edge_type: 'implements',
        is_primary_parent: true,
        status: 'confirmed',
        created_method: 'manual',
      })
    })
    expect(await screen.findByTestId('documents-create-relationships-recorded')).toBeInTheDocument()
    expect(screen.getByTestId('documents-create-relationship-7')).toHaveTextContent(
      'Incident Management Policy',
    )
    expect(onDone).not.toHaveBeenCalled()
    fireEvent.click(screen.getByTestId('documents-create-rel-done'))
    expect(onDone).toHaveBeenCalled()
  })

  it('allows skip without calling createEdge', () => {
    const onDone = vi.fn()
    render(
      <MemoryRouter>
        <DocumentCreateRelationshipsStep
          documentId={99}
          documentTitle="Incident Reporting SOP"
          onDone={onDone}
        />
      </MemoryRouter>,
    )
    fireEvent.click(screen.getByTestId('documents-create-rel-done'))
    expect(onDone).toHaveBeenCalled()
    expect(createEdge).not.toHaveBeenCalled()
  })
})
