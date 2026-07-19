import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'

const mockGetCampaignAnalytics = vi.fn()

vi.mock('react-i18next', () => ({
  initReactI18next: { type: '3rdParty', init: () => {} },
  useTranslation: () => ({
    t: (key: string, fallback?: string | { defaultValue?: string; count?: number }) => {
      if (typeof fallback === 'string') return fallback
      if (fallback && typeof fallback === 'object' && fallback.defaultValue) {
        return fallback.defaultValue.replace('{{count}}', String(fallback.count ?? ''))
      }
      return key
    },
  }),
}))

vi.mock('../../api/client', () => ({
  documentCampaignApi: {
    getCampaignAnalytics: (...args: unknown[]) => mockGetCampaignAnalytics(...args),
  },
  getApiErrorMessage: (err: unknown) => (err instanceof Error ? err.message : 'error'),
}))

describe('CampaignAnalyticsPanel', () => {
  beforeEach(() => {
    mockGetCampaignAnalytics.mockReset()
    mockGetCampaignAnalytics.mockResolvedValue({
      data: {
        campaign_id: 9,
        document_id: 3,
        require_quiz: true,
        funnel: {
          assigned: 10,
          opened: 8,
          quiz_attempted: 6,
          quiz_passed: 5,
          completed: 5,
        },
        score_histogram: [
          { bucket: '0-19', count: 0 },
          { bucket: '20-39', count: 1 },
          { bucket: '40-59', count: 0 },
          { bucket: '60-79', count: 2 },
          { bucket: '80-100', count: 3 },
        ],
        attempts_distribution: [
          { attempts: 1, count: 4 },
          { attempts: 2, count: 1 },
          { attempts: 3, count: 1 },
        ],
        time_to_complete_hours: { p50: 12, p90: 36 },
        reminder_sent_total: 7,
      },
    })
  })

  it('renders funnel and score histogram', async () => {
    const { CampaignAnalyticsPanel } = await import('../CampaignAnalyticsPanel')
    render(<CampaignAnalyticsPanel campaignId={9} />)

    await waitFor(() => {
      expect(screen.getByTestId('campaign-analytics-panel')).toBeInTheDocument()
    })
    expect(screen.getByText('Assigned')).toBeInTheDocument()
    expect(screen.getByText('10')).toBeInTheDocument()
    expect(screen.getByTestId('campaign-analytics-histogram')).toBeInTheDocument()
    expect(screen.getByTestId('campaign-analytics-attempts')).toBeInTheDocument()
    expect(mockGetCampaignAnalytics).toHaveBeenCalledWith(9)
  })
})
