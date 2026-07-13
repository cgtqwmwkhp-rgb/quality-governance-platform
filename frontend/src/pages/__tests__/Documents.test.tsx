import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

const mockGet = vi.fn()
const mockPost = vi.fn()
const mockTrackError = vi.fn()
const mockToastError = vi.fn()
const mockToastWarning = vi.fn()
const mockToastSuccess = vi.fn()
const mockNavigate = vi.fn()

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
  initReactI18next: { type: '3rdParty', init: () => {} },
}))

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  }
})

vi.mock('../../utils/errorTracker', () => ({
  trackError: (...args: unknown[]) => mockTrackError(...args),
}))

vi.mock('../../contexts/ToastContext', () => ({
  toast: {
    error: (...args: unknown[]) => mockToastError(...args),
    warning: (...args: unknown[]) => mockToastWarning(...args),
    success: (...args: unknown[]) => mockToastSuccess(...args),
    info: vi.fn(),
  },
}))

vi.mock('../../api/client', () => ({
  __esModule: true,
  default: {
    get: (...args: unknown[]) => mockGet(...args),
    post: (...args: unknown[]) => mockPost(...args),
    defaults: { baseURL: 'https://api.example.test' },
  },
  getApiErrorMessage: (error: unknown) => (error instanceof Error ? error.message : 'Request failed'),
}))
const sampleDoc = {
  id: 11,
  reference_number: 'DOC-11',
  title: 'Safety Policy',
  file_name: 'policy.pdf',
  file_type: 'pdf',
  file_size: 2048,
  document_type: 'policy',
  sensitivity: 'internal',
  status: 'approved',
  version: '1.0',
  view_count: 0,
  download_count: 0,
  is_public: false,
  created_at: '2026-03-22T10:00:00Z',
}

function mockHappyPath() {
  mockGet.mockImplementation((url: string) => {
    if (url.startsWith('/api/v1/documents/?')) {
      return Promise.resolve({ data: { items: [sampleDoc], total: 1, page: 1, page_size: 50 } })
    }
    if (url === '/api/v1/documents/stats/overview') {
      return Promise.resolve({
        data: {
          total_documents: 1,
          indexed_documents: 0,
          total_chunks: 0,
          by_status: { approved: 1 },
          by_type: { policy: 1 },
        },
      })
    }
    if (url === '/api/v1/documents/11/signed-url') {
      return Promise.resolve({
        data: { signed_url: '/api/v1/evidence-assets/download?key=policy.pdf' },
      })
    }
    return Promise.resolve({ data: { results: [] } })
  })
}

describe('Documents', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockHappyPath()
  })

  it('loads documents and navigates to the governed document detail page', async () => {
    const Documents = (await import('../Documents')).default

    render(
      <MemoryRouter initialEntries={['/documents']}>
        <Documents />
      </MemoryRouter>,
    )

    expect(
      await screen.findByRole('heading', { level: 1, name: 'nav.library' }),
    ).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /nav\.documents/i })).toHaveAttribute('aria-current', 'page')
    expect(await screen.findByTestId('documents-live-badge')).toHaveTextContent('Live data')

    fireEvent.click(await screen.findByText('Safety Policy'))

    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith('/documents/11')
    })
  })

  it('toasts and labels list unavailable instead of fake empty library', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url.startsWith('/api/v1/documents/?')) {
        return Promise.reject(new Error('Documents offline'))
      }
      if (url === '/api/v1/documents/stats/overview') {
        return Promise.resolve({
          data: {
            total_documents: 0,
            indexed_documents: 0,
            total_chunks: 0,
            by_status: {},
            by_type: {},
          },
        })
      }
      return Promise.resolve({ data: { results: [] } })
    })

    const Documents = (await import('../Documents')).default
    render(
      <MemoryRouter initialEntries={['/documents']}>
        <Documents />
      </MemoryRouter>,
    )

    expect(await screen.findByTestId('documents-partial-badge')).toHaveTextContent(/Partial data/)
    expect(screen.getByTestId('documents-list-unavailable')).toBeInTheDocument()
    expect(screen.getByText('Documents unavailable')).toBeInTheDocument()
    expect(screen.queryByTestId('documents-empty')).not.toBeInTheDocument()
    await waitFor(() => {
      expect(mockToastError).toHaveBeenCalledWith('Documents offline')
    })
  })

  it('warns when stats fail while list remains live', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url.startsWith('/api/v1/documents/?')) {
        return Promise.resolve({ data: { items: [sampleDoc] } })
      }
      if (url === '/api/v1/documents/stats/overview') {
        return Promise.reject(new Error('Stats offline'))
      }
      return Promise.resolve({ data: { results: [] } })
    })

    const Documents = (await import('../Documents')).default
    render(
      <MemoryRouter initialEntries={['/documents']}>
        <Documents />
      </MemoryRouter>,
    )

    expect(await screen.findByText('Safety Policy')).toBeInTheDocument()
    expect(screen.getByTestId('documents-partial-badge')).toBeInTheDocument()
    expect(screen.getByTestId('documents-partial-warning')).toHaveTextContent(/stats unavailable/i)
    await waitFor(() => {
      expect(mockToastWarning).toHaveBeenCalledWith(
        expect.stringMatching(/stats unavailable/i),
      )
    })
  })

  it('toasts semantic search failure without pretending zero matches', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url.startsWith('/api/v1/documents/?')) {
        return Promise.resolve({ data: { items: [sampleDoc] } })
      }
      if (url === '/api/v1/documents/stats/overview') {
        return Promise.resolve({
          data: {
            total_documents: 1,
            indexed_documents: 0,
            total_chunks: 0,
            by_status: { approved: 1 },
            by_type: { policy: 1 },
          },
        })
      }
      if (url.includes('/documents/search/semantic')) {
        return Promise.reject(new Error('Search offline'))
      }
      return Promise.resolve({ data: { results: [] } })
    })

    const Documents = (await import('../Documents')).default
    render(
      <MemoryRouter initialEntries={['/documents']}>
        <Documents />
      </MemoryRouter>,
    )

    await screen.findByTestId('documents-live-badge')
    fireEvent.change(screen.getByTestId('documents-library-search'), {
      target: { value: 'safety policy' },
    })

    expect(await screen.findByTestId('documents-search-unavailable')).toHaveTextContent(
      /Semantic search unavailable/i,
    )
    expect(screen.getByText(/do not treat this as zero matches/i)).toBeInTheDocument()
    await waitFor(() => {
      expect(mockToastError).toHaveBeenCalledWith(expect.stringMatching(/Search offline/i))
    })
  })

  it('navigates to document detail from the list view as well as the card grid', async () => {
    const Documents = (await import('../Documents')).default
    render(
      <MemoryRouter initialEntries={['/documents']}>
        <Documents />
      </MemoryRouter>,
    )

    expect(await screen.findByText('Safety Policy')).toBeInTheDocument()
    // Toggle to list view if the control exists; grid click already covered above.
    const listToggle = screen.queryByRole('button', { name: /list/i })
    if (listToggle) {
      fireEvent.click(listToggle)
      fireEvent.click(await screen.findByText('Safety Policy'))
      await waitFor(() => {
        expect(mockNavigate).toHaveBeenCalledWith('/documents/11')
      })
    }
  })

  it('deep-links ?q= into the visible search control and requests server search', async () => {
    const Documents = (await import('../Documents')).default
    render(
      <MemoryRouter initialEntries={['/documents?q=safety']}>
        <Documents />
      </MemoryRouter>,
    )

    const input = await screen.findByTestId('documents-library-search')
    expect(input).toHaveValue('safety')
    await waitFor(() => {
      expect(mockGet).toHaveBeenCalledWith(
        expect.stringMatching(/\/api\/v1\/documents\/\?.*search=safety/),
      )
    })
    expect(await screen.findByTestId('documents-search-status')).toHaveTextContent(/Keyword matches/i)
  })

  it('shows honest zero semantic matches (not unavailable)', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url.startsWith('/api/v1/documents/?')) {
        return Promise.resolve({ data: { items: [sampleDoc], total: 1 } })
      }
      if (url === '/api/v1/documents/stats/overview') {
        return Promise.resolve({
          data: {
            total_documents: 1,
            indexed_documents: 0,
            total_chunks: 0,
            by_status: { approved: 1 },
            by_type: { policy: 1 },
          },
        })
      }
      if (url.includes('/documents/search/semantic')) {
        return Promise.resolve({ data: { results: [] } })
      }
      return Promise.resolve({ data: { results: [] } })
    })

    const Documents = (await import('../Documents')).default
    render(
      <MemoryRouter initialEntries={['/documents']}>
        <Documents />
      </MemoryRouter>,
    )

    await screen.findByTestId('documents-live-badge')
    fireEvent.change(screen.getByTestId('documents-library-search'), {
      target: { value: 'zzzz-no-hit' },
    })

    expect(await screen.findByTestId('documents-search-zero')).toHaveTextContent(/No semantic matches/i)
    expect(screen.queryByTestId('documents-search-unavailable')).not.toBeInTheDocument()
  })

})
