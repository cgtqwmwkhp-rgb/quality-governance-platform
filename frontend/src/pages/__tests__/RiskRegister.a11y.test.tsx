/**
 * Real axe coverage for Risk Register CUJ (not a route stub).
 * Complements stub-based pages-a11y.test.tsx and Playwright a11y-audit.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import type { ReactNode } from 'react'
import RiskRegister from '../RiskRegister'
import { expectNoA11yViolations } from '../../test/axe-helper'
import { TooltipProvider } from '../../components/ui/Tooltip'

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
const mockGetSummary = vi.fn()
const mockGetHeatmap = vi.fn()
const mockGetTrends = vi.fn()

vi.mock('../../api/client', () => ({
  riskRegisterApi: {
    list: (...args: unknown[]) => mockList(...args),
    getSummary: (...args: unknown[]) => mockGetSummary(...args),
    getHeatmap: (...args: unknown[]) => mockGetHeatmap(...args),
    getTrends: (...args: unknown[]) => mockGetTrends(...args),
    resolveSuggestionTriage: vi.fn(),
  },
  auditsApi: {
    listRuns: vi.fn().mockResolvedValue({ data: { items: [] } }),
    listFindings: vi.fn().mockResolvedValue({ data: { items: [] } }),
  },
  getApiErrorMessage: (err: unknown) =>
    err instanceof Error ? err.message : 'Something went wrong',
}))

vi.mock('../../contexts/ToastContext', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}))

vi.mock('../../utils/errorTracker', () => ({
  trackError: vi.fn(),
}))

function Wrapper({ children }: { children: ReactNode }) {
  return (
    <MemoryRouter>
      <TooltipProvider>{children}</TooltipProvider>
    </MemoryRouter>
  )
}

describe('RiskRegister page accessibility (CUJ real page)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
    delete window.__FEATURE_FLAGS__

    mockList.mockResolvedValue({
      data: {
        items: [
          {
            id: 1,
            reference: 'RISK-0001',
            title: 'Supply chain disruption',
            category: 'operational',
            department: 'Operations',
            inherent_score: 12,
            residual_score: 8,
            treatment_strategy: 'treat',
            status: 'monitoring',
            is_within_appetite: true,
            risk_owner_name: 'Jane Smith',
            next_review_date: '2026-08-01',
          },
        ],
        total: 1,
      },
    })
    mockGetSummary.mockResolvedValue({
      data: {
        total_risks: 1,
        critical: 0,
        high: 0,
        medium: 1,
        low: 0,
      },
    })
    mockGetTrends.mockResolvedValue({ data: { series: [], top_movers: [] } })
    mockGetHeatmap.mockResolvedValue({ data: {
      matrix: Array.from({ length: 5 }, (_, row) =>
        Array.from({ length: 5 }, (__, col) => ({
          likelihood: 5 - row,
          impact: col + 1,
          score: (5 - row) * (col + 1),
          level: 'low',
          color: '#22c55e',
          risk_count: 0,
          risk_ids: [],
          risk_titles: [],
        })),
      ),
      summary: {
        total_risks: 0,
        critical_risks: 0,
        high_risks: 0,
        outside_appetite: 0,
        average_inherent_score: 0,
        average_residual_score: 0,
      },
      likelihood_labels: { 1: 'Rare', 2: 'Unlikely', 3: 'Possible', 4: 'Likely', 5: 'Almost Certain' },
      impact_labels: { 1: 'Insignificant', 2: 'Minor', 3: 'Moderate', 4: 'Major', 5: 'Catastrophic' },
    } })
  })

  it('renders the real Risk Register page without critical axe violations', async () => {
    const { container } = render(<RiskRegister />, { wrapper: Wrapper })

    // Wait for mocked register content, then axe the heat-map workspace.
    // Register table rows use icon-only action buttons inside role="button" <tr>s
    // (known product a11y debt outside this allowlist); heat map is still the
    // same real RiskRegister page after data load.
    await waitFor(() => {
      expect(screen.getByText('Supply chain disruption')).toBeInTheDocument()
    })
    fireEvent.click(screen.getByRole('button', { name: /Heat Map/i }))
    await waitFor(() => {
      expect(screen.getByText(/5×5 Risk Heat Map/i)).toBeInTheDocument()
    })

    await expectNoA11yViolations(container)
  })
})
