/**
 * Real axe coverage for the RTAs CUJ page (/rtas), not a route stub.
 * Complements stub-based pages-a11y.test.tsx (/rta) and Playwright a11y-audit.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import type { ReactNode } from 'react'
import RTAs from '../RTAs'
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
  rtasApi: {
    list: (...args: unknown[]) => mockList(...args),
    create: vi.fn(),
  },
  getApiErrorMessage: (err: unknown) =>
    err instanceof Error ? err.message : 'Something went wrong',
}))

vi.mock('../../utils/errorTracker', () => ({
  trackError: vi.fn(),
}))

function Wrapper({ children }: { children: ReactNode }) {
  return <MemoryRouter>{children}</MemoryRouter>
}

describe('RTAs page accessibility (real page /rtas)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockList.mockResolvedValue({
      data: {
        items: [
          {
            id: 1,
            reference_number: 'RTA-001',
            title: 'Junction collision on A1',
            description: 'Minor bumper contact at roundabout',
            severity: 'damage_only',
            status: 'reported',
            collision_date: '2026-06-01T09:00:00Z',
            reported_date: '2026-06-01T10:00:00Z',
            location: 'A1 northbound junction',
            driver_injured: false,
            police_attended: false,
            insurance_notified: false,
          },
        ],
        total: 1,
      },
    })
  })

  it('renders the populated RTAs register without axe violations', async () => {
    const { container } = render(<RTAs />, { wrapper: Wrapper })

    await waitFor(() => {
      expect(screen.getByText('RTA-001')).toBeInTheDocument()
    })

    await expectNoA11yViolations(container)
  })
})
