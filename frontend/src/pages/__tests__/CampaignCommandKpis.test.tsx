import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'

const mockGetComplianceOverview = vi.fn()

vi.mock('react-i18next', () => ({
  initReactI18next: { type: '3rdParty', init: () => {} },
  useTranslation: () => ({
    t: (key: string, fallback?: string | { defaultValue?: string; count?: number; completed?: number; opened?: number; overdue?: number }) => {
      if (typeof fallback === 'string') return fallback
      if (fallback && typeof fallback === 'object' && fallback.defaultValue) {
        return fallback.defaultValue
          .replace('{{count}}', String(fallback.count ?? ''))
          .replace('{{completed}}', String(fallback.completed ?? ''))
          .replace('{{opened}}', String(fallback.opened ?? ''))
          .replace('{{overdue}}', String(fallback.overdue ?? ''))
      }
      return key
    },
  }),
}))

vi.mock('../../api/client', () => ({
  documentCampaignApi: {
    getComplianceOverview: (...args: unknown[]) => mockGetComplianceOverview(...args),
  },
  getApiErrorMessage: (err: unknown) => (err instanceof Error ? err.message : 'error'),
}))

describe('CampaignCommandKpis', () => {
  beforeEach(() => {
    mockGetComplianceOverview.mockReset()
    mockGetComplianceOverview.mockResolvedValue({
      data: {
        active_campaigns: 3,
        total_assignments: 40,
        completed_assignments: 28,
        overall_completion_rate: 70,
        overdue_count: 4,
        quiz_fail_count: 2,
        unanswered_hseq_count: 1,
        open_rate: 55,
        series: [
          { date: '2026-07-05', completed: 2, opened: 3, overdue: 1 },
          { date: '2026-07-06', completed: 5, opened: 4, overdue: 0 },
        ],
      },
    })
  })

  it('renders portfolio KPI strip and trend rows', async () => {
    const { CampaignCommandKpis } = await import('../CampaignCommandKpis')
    render(<CampaignCommandKpis />)

    await waitFor(() => {
      expect(screen.getByTestId('campaign-command-kpis')).toBeInTheDocument()
    })
    expect(screen.getByText('Active campaigns')).toBeInTheDocument()
    expect(screen.getByText('3')).toBeInTheDocument()
    expect(screen.getByText('70%')).toBeInTheDocument()
    expect(screen.getByTestId('campaign-command-trend')).toBeInTheDocument()
    expect(mockGetComplianceOverview).toHaveBeenCalled()
  })
})
