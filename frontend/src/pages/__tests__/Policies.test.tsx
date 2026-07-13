import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

const mockList = vi.fn()

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
  initReactI18next: { type: '3rdParty', init: () => {} },
}))

vi.mock('../../utils/errorTracker', () => ({
  trackError: vi.fn(),
}))

vi.mock('../../api/client', () => ({
  policiesApi: {
    list: (...args: unknown[]) => mockList(...args),
    create: vi.fn(),
  },
  getApiErrorMessage: (error: unknown) =>
    error instanceof Error ? error.message : 'Request failed',
}))

describe('Policies', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockList.mockResolvedValue({
      data: {
        items: [
          {
            id: 3,
            reference_number: 'POL-3',
            title: 'Health and Safety Policy',
            document_type: 'policy',
            status: 'published',
            review_frequency_months: 12,
          },
        ],
      },
    })
  })

  it('loads policies inside the unified Library shell', async () => {
    const Policies = (await import('../Policies')).default

    render(
      <MemoryRouter initialEntries={['/policies']}>
        <Policies />
      </MemoryRouter>,
    )

    expect(await screen.findByRole('heading', { level: 1, name: 'nav.library' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /nav\.policies/i })).toHaveAttribute('aria-current', 'page')
    expect(await screen.findByText('Health and Safety Policy')).toBeInTheDocument()
  })
})
