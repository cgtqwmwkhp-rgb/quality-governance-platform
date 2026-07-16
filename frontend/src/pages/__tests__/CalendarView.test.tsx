import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

const mockGetFeed = vi.fn()

vi.mock('../../api/client', () => ({
  calendarApi: {
    getFeed: (...args: unknown[]) => mockGetFeed(...args),
  },
  getApiErrorMessage: (err: unknown) => (err instanceof Error ? err.message : 'error'),
}))

vi.mock('../../contexts/ToastContext', () => ({
  toast: { error: vi.fn(), success: vi.fn(), warning: vi.fn(), info: vi.fn() },
}))

describe('CalendarView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockGetFeed.mockResolvedValue({
      data: {
        start: '2026-07-01',
        end: '2026-07-31',
        generated_at: '2026-07-16T00:00:00Z',
        total: 1,
        events: [
          {
            id: 'audit_run:1',
            title: 'Plant audit',
            type: 'audit',
            date: '2026-07-20',
            status: 'upcoming',
            source_module: 'audit_run',
            source_id: '1',
            href: '/audits/1/execute',
          },
        ],
        sources_ok: ['audit_runs'],
        sources_failed: [],
      },
    })
  })

  it('loads live feed and shows add-event chooser (audit / action)', async () => {
    const CalendarView = (await import('../CalendarView')).default
    render(
      <MemoryRouter initialEntries={['/calendar']}>
        <Routes>
          <Route path="/calendar" element={<CalendarView />} />
        </Routes>
      </MemoryRouter>,
    )

    expect(await screen.findByTestId('governance-calendar')).toBeInTheDocument()
    await waitFor(() => expect(mockGetFeed).toHaveBeenCalled())
    expect(await screen.findByTestId('calendar-chip-audit_run:1')).toHaveTextContent('Plant audit')

    fireEvent.click(screen.getByTestId('calendar-add-event'))
    expect(screen.getByRole('link', { name: /Schedule audit/i })).toHaveAttribute('href', '/audits')
    expect(screen.getByRole('link', { name: /Create action/i })).toHaveAttribute('href', '/actions')
  })
})
