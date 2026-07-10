/**
 * Real axe coverage for the Investigations CUJ page (/investigations), not a route stub.
 * Complements Investigations.test.tsx and Playwright a11y-audit.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import type { ReactNode } from 'react'
import Investigations from '../Investigations'
import { expectNoA11yViolations } from '../../test/axe-helper'

const mockNavigate = vi.fn()

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => {
      const translations: Record<string, string> = {
        'investigations.title': 'Investigations',
        'investigations.subtitle': 'Root cause analysis and corrective actions',
        'investigations.new': 'New Investigation',
        'investigations.search_placeholder': 'Search investigations...',
        'investigations.empty.title': 'No investigations yet',
        'investigations.stats.total': 'Total',
        'investigations.stats.completed': 'Completed',
        'status.in_progress': 'In Progress',
      }
      return translations[key] || key
    },
    i18n: { language: 'en' },
  }),
  initReactI18next: { type: '3rdParty', init: () => {} },
}))

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return { ...actual, useNavigate: () => mockNavigate }
})

vi.mock('../../api/client', () => ({
  investigationsApi: {
    list: vi.fn(),
    create: vi.fn(),
    get: vi.fn(),
    update: vi.fn(),
    createFromRecord: vi.fn(),
    listSourceRecords: vi.fn(),
  },
  actionsApi: {
    list: vi.fn(),
    create: vi.fn(),
    get: vi.fn(),
    update: vi.fn(),
  },
  getApiErrorMessage: (err: unknown) =>
    err instanceof Error ? err.message : 'Unknown error',
}))

vi.mock('../../utils/errorTracker', () => ({
  trackError: vi.fn(),
}))

vi.mock('../../components/UserEmailSearch', () => ({
  UserEmailSearch: ({
    value,
    onChange,
    label,
  }: {
    value?: string
    onChange?: (v: string) => void
    label?: string
  }) => (
    <div>
      <label>{label}</label>
      <input
        data-testid="user-email-search"
        value={value}
        onChange={(e) => onChange?.(e.target.value)}
      />
    </div>
  ),
}))

function Wrapper({ children }: { children: ReactNode }) {
  return <BrowserRouter>{children}</BrowserRouter>
}

describe('Investigations page accessibility (real page /investigations)', () => {
  beforeEach(async () => {
    vi.clearAllMocks()
    mockNavigate.mockClear()
    const client = await import('../../api/client')
    ;(client.investigationsApi.list as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: {
        items: [
          {
            id: 1,
            reference_number: 'INV-001',
            template_id: 1,
            assigned_entity_type: 'road_traffic_collision',
            assigned_entity_id: 10,
            status: 'in_progress',
            title: 'Vehicle collision on A1 motorway',
            description: 'Investigating root cause of collision',
            data: {},
            created_at: '2026-02-01T00:00:00Z',
          },
        ],
        total: 1,
        page: 1,
        page_size: 10,
        pages: 1,
      },
    })
    ;(client.actionsApi.list as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: { items: [], total: 0, page: 1, page_size: 10, pages: 0 },
    })
  })

  it('renders the real Investigations page without critical axe violations', async () => {
    const { container } = render(<Investigations />, { wrapper: Wrapper })
    await waitFor(() => {
      expect(screen.getByText('Vehicle collision on A1 motorway')).toBeInTheDocument()
    })
    await expectNoA11yViolations(container)
  })
})
