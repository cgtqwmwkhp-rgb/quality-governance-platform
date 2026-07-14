/**
 * Real axe coverage for CUJ-09 Complaints list page (not a route stub).
 * Complements stub-based pages-a11y.test.tsx and Playwright a11y-audit.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import type { ReactNode } from 'react'
import Complaints from '../Complaints'
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
  complaintsApi: {
    list: (...args: unknown[]) => mockList(...args),
    create: vi.fn(),
  },
  notificationsApi: {
    getDeliveryStatus: vi.fn().mockResolvedValue({ data: { email_configured: true } }),
  },
  getApiErrorMessage: (err: unknown) =>
    err instanceof Error ? err.message : 'Something went wrong',
}))

vi.mock('../../contexts/ToastContext', () => ({
  toast: { error: vi.fn(), success: vi.fn() },
}))

vi.mock('../../utils/errorTracker', () => ({
  trackError: vi.fn(),
}))

function Wrapper({ children }: { children: ReactNode }) {
  return <MemoryRouter>{children}</MemoryRouter>
}

describe('Complaints page accessibility (CUJ-09 real page)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockList.mockResolvedValue({
      data: {
        items: [
          {
            id: 1,
            reference_number: 'CMP-001',
            title: 'Late delivery issue',
            description: 'Package arrived two weeks late',
            complaint_type: 'delivery',
            priority: 'high',
            status: 'received',
            received_date: '2026-02-10T09:00:00Z',
            complainant_name: 'John Doe',
            complainant_email: 'john@example.com',
            complainant_phone: '',
          },
        ],
        total: 1,
        page: 1,
        page_size: 50,
        total_pages: 1,
      },
    })
  })

  it('renders the real Complaints page without critical axe violations', async () => {
    const { container } = render(<Complaints />, { wrapper: Wrapper })
    await waitFor(() => {
      expect(screen.getByText('CMP-001')).toBeInTheDocument()
    })
    await expectNoA11yViolations(container)
  })
})
