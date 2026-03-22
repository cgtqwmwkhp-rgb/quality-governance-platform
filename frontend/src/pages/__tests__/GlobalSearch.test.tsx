import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'

const mockSearch = vi.fn()

vi.mock('../../api/client', () => ({
  searchApi: {
    search: (...args: unknown[]) => mockSearch(...args),
  },
  getApiErrorMessage: (error: unknown) => (error instanceof Error ? error.message : 'Search failed'),
}))

vi.mock('../../contexts/ToastContext', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}))

describe('GlobalSearch', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockSearch.mockResolvedValue({
      data: {
        total: 2,
        query: 'policy',
        facets: { modules: { Documents: 1, Incidents: 1 } },
        results: [
          {
            id: 'DOC-1',
            type: 'document',
            title: 'Controlled Policy',
            description: 'Documented approval process',
            module: 'Documents',
            status: 'completed',
            date: '2026-03-20T10:00:00Z',
            relevance: 95,
            highlights: ['policy'],
          },
          {
            id: 'INC-1',
            type: 'incident',
            title: 'Policy breach incident',
            description: 'An incident linked to an outdated policy',
            module: 'Incidents',
            status: 'open',
            date: '2026-03-18T10:00:00Z',
            relevance: 80,
            highlights: ['policy'],
          },
        ],
      },
    })
  })

  it('searches via the live API client and applies module filters', async () => {
    const GlobalSearch = (await import('../GlobalSearch')).default

    render(<GlobalSearch />)

    fireEvent.change(screen.getByPlaceholderText(/Search incidents/i), {
      target: { value: 'policy' },
    })
    fireEvent.click(screen.getByRole('button', { name: /^Search$/ }))

    expect(await screen.findByText('Controlled Policy')).toBeInTheDocument()
    expect(mockSearch).toHaveBeenCalledWith({ q: 'policy', page: 1, page_size: 100 })

    fireEvent.click(screen.getByRole('button', { name: 'Toggle filters' }))
    fireEvent.click(screen.getByRole('button', { name: 'Documents' }))

    await waitFor(() => {
      expect(screen.getByText('Controlled Policy')).toBeInTheDocument()
      expect(screen.queryByText('Policy breach incident')).not.toBeInTheDocument()
    })
  })
})
