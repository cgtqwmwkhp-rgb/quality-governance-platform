/**
 * Real axe coverage for the Incidents CUJ page (/incidents), not a route stub.
 * Covers the populated register and the report-incident dialog.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import type { ReactNode } from 'react'
import Incidents from '../Incidents'
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

vi.mock('../../api/client', () => ({
  incidentsApi: {
    list: (...args: unknown[]) => mockList(...args),
    create: vi.fn(),
  },
  notificationsApi: {
    getDeliveryStatus: vi.fn().mockResolvedValue({ data: { email_configured: false } }),
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

describe('Incidents page accessibility (real page /incidents)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockList.mockResolvedValue({
      data: {
        items: [
          {
            id: 1,
            reference_number: 'INC-001',
            title: 'Slip in warehouse',
            description: 'Worker slipped on wet floor',
            incident_type: 'injury',
            severity: 'high',
            status: 'reported',
            incident_date: '2026-02-15T10:00:00Z',
            reported_date: '2026-02-15T11:00:00Z',
            created_at: '2026-02-15T11:00:00Z',
          },
        ],
        total: 1,
        page: 1,
        page_size: 50,
        total_pages: 1,
      },
    })
  })

  it('renders the populated Incidents register without axe violations', async () => {
    const { container } = render(<Incidents />, { wrapper: Wrapper })

    await waitFor(() => {
      expect(screen.getByText('INC-001')).toBeInTheDocument()
    })

    await expectNoA11yViolations(container)
  })

  it('opens the real report-incident dialog without axe violations', async () => {
    const { baseElement } = render(<Incidents />, { wrapper: Wrapper })

    await waitFor(() => {
      expect(screen.getByText('INC-001')).toBeInTheDocument()
    })
    fireEvent.click(screen.getByRole('button', { name: 'incidents.new' }))

    await waitFor(() => {
      expect(screen.getByRole('dialog')).toBeInTheDocument()
    })

    await expectNoA11yViolations(baseElement)
  })
})
