/**
 * Real axe coverage for the Near Misses CUJ page (/near-misses), not a route stub.
 * Covers the populated register and the report-near-miss dialog.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import type { ReactNode } from 'react'
import NearMisses from '../NearMisses'
import { expectNoA11yViolations } from '../../test/axe-helper'

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return { ...actual, useNavigate: () => vi.fn() }
})

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, fallback?: string) => fallback ?? key,
    i18n: { language: 'en' },
  }),
  initReactI18next: { type: '3rdParty', init: () => {} },
}))

const mockList = vi.fn()
const mockCustomersList = vi.fn()

vi.mock('../../api/client', () => ({
  nearMissesApi: {
    list: (...args: unknown[]) => mockList(...args),
    create: vi.fn(),
  },
  lookupsApi: {
    list: (...args: unknown[]) => mockCustomersList(...args),
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

describe('Near Misses page accessibility (real page /near-misses)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockCustomersList.mockImplementation((category: string) => {
      if (category === 'severity_levels') {
        return Promise.resolve({
          items: [
            {
              id: 2,
              code: 'high',
              label: 'High impact',
              description: null,
              is_active: true,
              display_order: 1,
            },
          ],
          total: 1,
        })
      }
      return Promise.resolve({
        items: [
          {
            id: 1,
            code: 'ukpn',
            label: 'UK Power Networks',
            description: 'UKPN',
            is_active: true,
            display_order: 1,
          },
        ],
        total: 1,
      })
    })
    mockList.mockResolvedValue({
      data: {
        items: [
          {
            id: 17,
            reference_number: 'NM-00017',
            reporter_name: 'Alex Morgan',
            contract: 'North Depot',
            location: 'Loading bay 3',
            event_date: '2026-07-09T08:30:00Z',
            description: 'A pallet shifted while being moved.',
            potential_severity: 'high',
            status: 'reported',
            was_involved: true,
            witnesses_present: false,
          },
        ],
        total: 1,
        page: 1,
        page_size: 50,
        total_pages: 1,
      },
    })
  })

  it('renders the populated Near Misses register without axe violations', async () => {
    const { container } = render(<NearMisses />, { wrapper: Wrapper })

    await waitFor(() => {
      expect(screen.getByText('NM-00017')).toBeInTheDocument()
    })

    await expectNoA11yViolations(container)
  })

  it('opens the real report-near-miss dialog without axe violations', async () => {
    const { baseElement } = render(<NearMisses />, { wrapper: Wrapper })

    await waitFor(() => {
      expect(screen.getByText('NM-00017')).toBeInTheDocument()
    })
    fireEvent.click(screen.getByRole('button', { name: 'near_misses.new' }))

    await waitFor(() => {
      expect(screen.getByRole('dialog')).toBeInTheDocument()
    })

    await expectNoA11yViolations(baseElement)
  })

  it('loads the severity lookup when the create dialog opens', async () => {
    render(<NearMisses />, { wrapper: Wrapper })

    await waitFor(() => {
      expect(screen.getByText('NM-00017')).toBeInTheDocument()
    })
    fireEvent.click(screen.getByRole('button', { name: 'near_misses.new' }))

    await waitFor(() => {
      expect(mockCustomersList).toHaveBeenCalledWith('severity_levels', true)
    })
    expect(document.getElementById('near-miss-potential-severity')).toBeInTheDocument()
  })
})
