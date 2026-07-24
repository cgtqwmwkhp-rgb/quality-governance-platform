import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

const mockSearch = vi.fn()
const mockInterpret = vi.fn()

vi.mock('../../../api/client', () => ({
  searchApi: {
    search: (...args: unknown[]) => mockSearch(...args),
    interpret: (...args: unknown[]) => mockInterpret(...args),
  },
  getApiErrorMessage: (error: unknown) => (error instanceof Error ? error.message : 'Search failed'),
}))

vi.mock('../../../contexts/ToastContext', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}))

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (_key: string, fallback?: string) => fallback ?? _key,
    i18n: { language: 'en' },
  }),
  initReactI18next: { type: '3rdParty', init: () => {} },
}))

describe('GlobalSearchPalette', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockInterpret.mockResolvedValue({
      data: {
        q: 'policy',
        module: null,
        status: null,
        date_from: null,
        date_to: null,
        navigate: null,
        label: null,
        source: 'keyword',
      },
    })
    mockSearch.mockResolvedValue({
      data: {
        total: 1,
        query: 'policy',
        facets: { modules: { Documents: 1 } },
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
            entity_id: 1,
            path: '/documents/1',
          },
        ],
      },
    })
  })

  it('closes on Escape and navigates when a result is selected', async () => {
    const user = userEvent.setup()
    const onOpenChange = vi.fn()
    const GlobalSearchPalette = (await import('../GlobalSearchPalette')).default

    render(
      <MemoryRouter initialEntries={['/rtas/5']}>
        <Routes>
          <Route
            path="*"
            element={<GlobalSearchPalette open onOpenChange={onOpenChange} />}
          />
        </Routes>
      </MemoryRouter>,
    )

    expect(screen.getByRole('dialog')).toBeInTheDocument()

    await user.keyboard('{Escape}')
    expect(onOpenChange).toHaveBeenCalledWith(false)

    onOpenChange.mockClear()
    fireEvent.change(screen.getByPlaceholderText(/Search incidents/i), {
      target: { value: 'policy' },
    })
    fireEvent.click(screen.getByRole('button', { name: /^Search$/ }))

    expect(await screen.findByText('Controlled Policy')).toBeInTheDocument()
    await user.click(screen.getByText('Controlled Policy'))

    await waitFor(() => {
      expect(onOpenChange).toHaveBeenCalledWith(false)
    })
  })

  it('runs a structured suggestion search for high-priority incidents', async () => {
    const user = userEvent.setup()
    const GlobalSearchPalette = (await import('../GlobalSearchPalette')).default

    render(
      <MemoryRouter>
        <GlobalSearchPalette open onOpenChange={vi.fn()} />
      </MemoryRouter>,
    )

    await user.click(screen.getByText('High-priority incidents'))

    await waitFor(() => {
      expect(mockSearch).toHaveBeenCalledWith(
        expect.objectContaining({
          q: 'critical high',
          module: 'Incidents',
        }),
      )
    })
  })
})
