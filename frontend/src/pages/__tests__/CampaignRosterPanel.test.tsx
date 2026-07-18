import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'

const mockListCampaignRoster = vi.fn()

vi.mock('react-i18next', () => ({
  initReactI18next: { type: '3rdParty', init: () => {} },
  useTranslation: () => ({
    t: (key: string, fallback?: string | { defaultValue?: string; shown?: number; total?: number }) => {
      if (typeof fallback === 'string') return fallback
      if (fallback && typeof fallback === 'object' && fallback.defaultValue) {
        return fallback.defaultValue
          .replace('{{shown}}', String(fallback.shown ?? ''))
          .replace('{{total}}', String(fallback.total ?? ''))
      }
      return key
    },
  }),
}))

vi.mock('../../api/client', () => ({
  documentCampaignApi: {
    listCampaignRoster: (...args: unknown[]) => mockListCampaignRoster(...args),
  },
  getApiErrorMessage: (err: unknown) => (err instanceof Error ? err.message : 'error'),
}))

describe('CampaignRosterPanel', () => {
  beforeEach(() => {
    mockListCampaignRoster.mockReset()
    mockListCampaignRoster.mockResolvedValue({
      data: {
        campaign_id: 9,
        document_id: 3,
        require_quiz: true,
        total: 1,
        limit: 100,
        offset: 0,
        summary: {
          assigned: 4,
          completed: 1,
          pending: 1,
          overdue: 2,
          expired: 0,
          opened: 2,
          not_opened: 2,
          quiz_pass_count: 1,
          quiz_fail_count: 1,
          completion_rate: 25,
          open_rate: 50,
        },
        items: [
          {
            assignment_id: 1,
            user_id: 5,
            user_email: 'alex@example.com',
            user_name: 'Alex Engineer',
            status: 'overdue',
            assigned_at: '2026-07-01T00:00:00Z',
            due_at: '2026-07-10T00:00:00Z',
            first_opened_at: null,
            completed_at: null,
            quiz_score: null,
            quiz_passed: null,
            quiz_attempts: 0,
            reminders_sent: 2,
            last_reminder_at: null,
          },
        ],
      },
    })
  })

  it('renders KPI strip and assignee roster rows', async () => {
    const { CampaignRosterPanel } = await import('../CampaignRosterPanel')
    render(<CampaignRosterPanel campaignId={9} />)

    await waitFor(() => {
      expect(screen.getByText('Alex Engineer')).toBeInTheDocument()
    })
    expect(screen.getByTestId('campaign-roster-kpis')).toBeInTheDocument()
    expect(screen.getByText('alex@example.com')).toBeInTheDocument()
    expect(screen.getByTestId('campaign-roster-total')).toBeInTheDocument()
    expect(mockListCampaignRoster).toHaveBeenCalledWith(9, expect.objectContaining({ limit: 100 }))
  })
})
