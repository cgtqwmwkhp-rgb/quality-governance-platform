/**
 * Real axe coverage for the RTA detail CUJ page (/rtas/:id), not a route stub.
 * Complements RTAs.a11y.test.tsx (list) and Playwright rta-lifecycle-cuj.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import type { ReactNode } from 'react'
import RTADetail from '../RTADetail'
import { expectNoA11yViolations } from '../../test/axe-helper'

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, fallbackOrOptions?: string | Record<string, unknown>) => {
      if (typeof fallbackOrOptions === 'string') return fallbackOrOptions
      if (fallbackOrOptions && typeof fallbackOrOptions === 'object' && 'defaultValue' in fallbackOrOptions) {
        return String(fallbackOrOptions.defaultValue)
      }
      return key
    },
    i18n: { language: 'en' },
  }),
  initReactI18next: { type: '3rdParty', init: () => {} },
}))

vi.mock('../../contexts/ToastContext', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}))

vi.mock('../../utils/errorTracker', () => ({
  trackError: vi.fn(),
}))

vi.mock('../../components/ui/Breadcrumbs', () => ({
  Breadcrumbs: () => <nav aria-label="Breadcrumb" data-testid="breadcrumbs" />,
}))

vi.mock('../../components/UserEmailSearch', () => ({
  UserEmailSearch: () => <div data-testid="user-email-search" />,
}))

vi.mock('../../api/client', () => ({
  rtasApi: {
    get: vi.fn(),
    listInvestigations: vi.fn(),
    listRunningSheet: vi.fn(),
    update: vi.fn(),
    addRunningSheetEntry: vi.fn(),
    deleteRunningSheetEntry: vi.fn(),
  },
  investigationsApi: { createFromRecord: vi.fn() },
  actionsApi: { list: vi.fn(), create: vi.fn(), update: vi.fn() },
  evidenceAssetsApi: { list: vi.fn(), upload: vi.fn(), delete: vi.fn() },
  getApiErrorMessage: (err: unknown) =>
    err instanceof Error ? err.message : 'Something went wrong',
}))

const mockRta = {
  id: 42,
  reference_number: 'RTA-042',
  title: 'Junction collision on A1',
  description: 'Minor bumper contact at roundabout',
  severity: 'damage_only',
  status: 'reported',
  collision_date: '2026-06-01T09:00:00Z',
  reported_date: '2026-06-01T10:00:00Z',
  location: 'A1 northbound junction',
  driver_name: 'Alex Driver',
  reporter_name: 'Alex Driver',
  driver_injured: false,
  police_attended: false,
  insurance_notified: false,
  created_at: '2026-06-01T10:05:00Z',
}

function Wrapper({ children }: { children: ReactNode }) {
  return (
    <MemoryRouter initialEntries={['/rtas/42']}>
      <Routes>
        <Route path="/rtas/:id" element={children} />
      </Routes>
    </MemoryRouter>
  )
}

describe('RTADetail page accessibility (real page /rtas/:id)', () => {
  beforeEach(async () => {
    vi.clearAllMocks()
    const client = await import('../../api/client')
    client.rtasApi.get.mockResolvedValue({ data: mockRta })
    client.rtasApi.listInvestigations.mockResolvedValue({ data: { items: [], total: 0 } })
    client.rtasApi.listRunningSheet.mockResolvedValue({ data: [] })
    client.actionsApi.list.mockResolvedValue({ data: { items: [] } })
    client.evidenceAssetsApi.list.mockResolvedValue({ data: { items: [] } })
  })

  it('renders populated RTA detail without axe violations', async () => {
    const { container } = render(<RTADetail />, { wrapper: Wrapper })

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Junction collision on A1' })).toBeInTheDocument()
    })

    expect(screen.getByTestId('rta-key-dates')).toBeInTheDocument()
    await expectNoA11yViolations(container)
  })
})
