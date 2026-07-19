import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

const mockListCompliancePeople = vi.fn()

vi.mock('react-i18next', () => ({
  initReactI18next: { type: '3rdParty', init: () => {} },
  useTranslation: () => ({
    t: (key: string, fallback?: string | { defaultValue?: string; id?: number; shown?: number; total?: number }) => {
      if (typeof fallback === 'string') return fallback
      if (fallback && typeof fallback === 'object' && fallback.defaultValue) {
        return fallback.defaultValue
          .replace('{{id}}', String(fallback.id ?? ''))
          .replace('{{shown}}', String(fallback.shown ?? ''))
          .replace('{{total}}', String(fallback.total ?? ''))
      }
      return key
    },
  }),
}))

vi.mock('../../api/client', () => ({
  documentCampaignApi: {
    listCompliancePeople: (...args: unknown[]) => mockListCompliancePeople(...args),
  },
  getApiErrorMessage: (err: unknown) => (err instanceof Error ? err.message : 'error'),
}))

describe('CampaignPeopleChase', () => {
  beforeEach(() => {
    mockListCompliancePeople.mockReset()
    mockListCompliancePeople.mockResolvedValue({
      data: {
        items: [
          {
            assignment_id: 1,
            campaign_id: 9,
            document_id: 3,
            document_title: 'Safety Policy',
            user_id: 5,
            user_name: 'Alex Engineer',
            user_email: 'alex@example.com',
            status: 'overdue',
            quiz_score: null,
            quiz_passed: null,
            quiz_attempts: 0,
            first_opened_at: null,
            completed_at: null,
            due_at: '2026-07-10T00:00:00Z',
            reminders_sent: 2,
          },
        ],
        total: 1,
        limit: 50,
        offset: 0,
      },
    })
  })

  it('renders overdue chase rows with results link', async () => {
    const { CampaignPeopleChase } = await import('../CampaignPeopleChase')
    render(
      <MemoryRouter>
        <CampaignPeopleChase />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByText('Alex Engineer')).toBeInTheDocument()
    })
    expect(screen.getByTestId('campaign-people-chase')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Open results' })).toHaveAttribute(
      'href',
      '/documents/3?tab=campaign-results&campaignId=9',
    )
    expect(mockListCompliancePeople).toHaveBeenCalledWith(
      expect.objectContaining({ status: 'overdue', limit: 50 }),
    )
  })
})
