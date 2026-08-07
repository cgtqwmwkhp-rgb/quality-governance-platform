import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import type { DocumentThreadResponse } from '../../../api/documentGraphClient'
import { DocumentThreadStrip } from '../DocumentThreadStrip'

const getThread = vi.fn()
const flagState: Record<string, boolean> = {
  document_graph_thread_ambient: false,
}

vi.mock('../../../api/client', () => ({
  documentGraphApi: {
    getThread: (...args: unknown[]) => getThread(...args),
  },
  getApiErrorMessage: (err: unknown) => (err as Error)?.message ?? 'error',
}))

vi.mock('../../../hooks/useFeatureFlag', () => ({
  useFeatureFlag: (key: string) => Boolean(flagState[key]),
}))

function threadResponse(): DocumentThreadResponse {
  return {
    document_id: 10,
    max_depth: 4,
    ancestors: [
      {
        document_id: 1,
        edge_id: 11,
        depth: 1,
        direction: 'parent',
        title: 'IM Policy',
        reference: 'POL-1',
        href: '/documents/1',
        origin: 'graph',
        status: 'confirmed',
      },
    ],
    descendants: [],
  }
}

describe('DocumentThreadStrip', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    flagState.document_graph_thread_ambient = false
    getThread.mockResolvedValue({ data: threadResponse() })
  })

  it('is invisible and does not fetch when the ambient flag is off', () => {
    const { container } = render(
      <MemoryRouter>
        <DocumentThreadStrip
          documentId={10}
          documentTitle="SOP"
          documentReference="SOP-10"
          documentGraphEnabled
        />
      </MemoryRouter>,
    )
    expect(container).toBeEmptyDOMElement()
    expect(screen.queryByTestId('document-thread-strip')).not.toBeInTheDocument()
    expect(getThread).not.toHaveBeenCalled()
  })

  it('renders enriched confirmed hops when the ambient flag is on', async () => {
    flagState.document_graph_thread_ambient = true
    render(
      <MemoryRouter>
        <DocumentThreadStrip
          documentId={10}
          documentTitle="Reporting SOP"
          documentReference="SOP-10"
          documentGraphEnabled
        />
      </MemoryRouter>,
    )

    expect(screen.getByTestId('document-thread-strip')).toBeInTheDocument()
    await waitFor(() => expect(getThread).toHaveBeenCalledWith(10))
    expect(getThread.mock.calls[0]).toEqual([10])
    expect(await screen.findByTestId('document-thread-strip-hop-1')).toHaveTextContent('IM Policy')
    expect(screen.getByTestId('document-thread-strip-current')).toHaveTextContent('Reporting SOP')
  })

  it('does not fetch when master Doc Graph is closed even if ambient is on', () => {
    flagState.document_graph_thread_ambient = true
    render(
      <MemoryRouter>
        <DocumentThreadStrip
          documentId={10}
          documentTitle="SOP"
          documentGraphEnabled={false}
        />
      </MemoryRouter>,
    )
    expect(screen.getByTestId('document-thread-strip')).toBeInTheDocument()
    expect(getThread).not.toHaveBeenCalled()
    expect(screen.getByTestId('document-thread-strip-empty')).toBeInTheDocument()
  })
})
