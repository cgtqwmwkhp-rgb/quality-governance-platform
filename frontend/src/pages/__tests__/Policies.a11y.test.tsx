/**
 * Real axe coverage for the Policies CUJ page (/policies), not a route stub.
 * Covers the populated register and the W5 migration guidance (create path removed).
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import type { ReactNode } from 'react'
import Policies from '../Policies'
import { expectNoA11yViolations } from '../../test/axe-helper'

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return { ...actual, useNavigate: () => vi.fn() }
})

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, fallback?: string | { defaultValue?: string }) => {
      if (typeof fallback === 'string') return fallback
      if (fallback && typeof fallback === 'object' && fallback.defaultValue) {
        return fallback.defaultValue
      }
      return key
    },
    i18n: { language: 'en' },
  }),
  initReactI18next: { type: '3rdParty', init: () => {} },
}))

const mockList = vi.fn()

vi.mock('../../api/client', () => ({
  policiesApi: {
    list: (...args: unknown[]) => mockList(...args),
    create: vi.fn(),
  },
  getApiErrorMessage: (error: unknown) =>
    error instanceof Error ? error.message : 'Something went wrong',
}))

vi.mock('../../utils/errorTracker', () => ({
  trackError: vi.fn(),
}))

function Wrapper({ children }: { children: ReactNode }) {
  return <MemoryRouter>{children}</MemoryRouter>
}

describe('Policies page accessibility (real page /policies)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockList.mockResolvedValue({
      data: {
        items: [
          {
            id: 1,
            reference_number: 'POL-001',
            title: 'Quality Manual',
            description: 'Top-level quality policy',
            document_type: 'policy',
            status: 'published',
            review_frequency_months: 12,
            is_public: false,
            created_at: '2026-01-15T10:00:00Z',
          },
        ],
        total: 1,
      },
    })
  })

  it('renders the populated Policies register without axe violations', async () => {
    const { container } = render(<Policies />, { wrapper: Wrapper })

    await waitFor(() => {
      expect(screen.getByText('POL-001')).toBeInTheDocument()
    })

    await expectNoA11yViolations(container)
  })

  it('shows migration guidance without a create-policy control and without axe violations', async () => {
    const { container } = render(<Policies />, { wrapper: Wrapper })

    await waitFor(() => {
      expect(screen.getByText('POL-001')).toBeInTheDocument()
    })

    expect(screen.queryByRole('button', { name: 'policies.new' })).not.toBeInTheDocument()
    expect(screen.getByText(/Policy CRUD is frozen/i)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Governance Library' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Document Control' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'HSEQ Campaigns' })).toBeInTheDocument()

    await expectNoA11yViolations(container)
  })
})
