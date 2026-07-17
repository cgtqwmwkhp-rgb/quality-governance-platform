import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

const mockGetFeed = vi.fn()

const { t } = vi.hoisted(() => ({
  t: (key: string, options?: string | Record<string, unknown>) => {
    if (typeof options === 'string') return options
    if (options && typeof options === 'object') {
      const template = typeof options.defaultValue === 'string' ? options.defaultValue : key
      return template.replace(/\{\{(\w+)\}\}/g, (_, name: string) =>
        String(options[name] ?? `{{${name}}}`),
      )
    }
    return key
  },
}))

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t,
    i18n: { language: 'en' },
  }),
  initReactI18next: { type: '3rdParty', init: () => {} },
}))

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
        total: 2,
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
          {
            id: 'capa:9',
            title: 'Fix guard rail',
            type: 'deadline',
            date: '2026-07-22',
            status: 'upcoming',
            source_module: 'capa_action',
            source_id: '9',
            href: '/actions?sourceType=capa&sourceId=9',
          },
        ],
        sources_ok: ['audit_runs', 'capa_actions'],
        sources_failed: [],
      },
    })
  })

  it('loads live feed, KPI counts, and add-event chooser (audit / action)', async () => {
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
    expect(screen.getByTestId('calendar-kpi-audits')).toHaveTextContent('1')
    expect(screen.getByTestId('calendar-kpi-actions')).toHaveTextContent('1')

    fireEvent.click(screen.getByTestId('calendar-add-event'))
    const scheduleLinks = screen.getAllByRole('link', { name: 'calendar.schedule_audit' })
    const menuScheduleLink = scheduleLinks.find((el) => el.className.includes('hover:bg-accent'))
    expect(menuScheduleLink).toHaveAttribute('href', '/audits')
    const actionLinks = screen.getAllByRole('link', { name: 'calendar.create_action' })
    const menuActionLink = actionLinks.find((el) => el.className.includes('hover:bg-accent'))
    expect(menuActionLink).toHaveAttribute('href', '/actions')
  })

  it('shows honest empty agenda with audit/action CTAs when feed is empty', async () => {
    mockGetFeed.mockResolvedValue({
      data: {
        start: '2026-07-01',
        end: '2026-07-31',
        generated_at: '2026-07-16T00:00:00Z',
        total: 0,
        events: [],
        sources_ok: ['audit_runs', 'capa_actions'],
        sources_failed: [],
      },
    })

    const CalendarView = (await import('../CalendarView')).default
    render(
      <MemoryRouter initialEntries={['/calendar?view=agenda']}>
        <Routes>
          <Route path="/calendar" element={<CalendarView />} />
        </Routes>
      </MemoryRouter>,
    )

    expect(await screen.findByTestId('calendar-empty-agenda')).toBeInTheDocument()
    expect(screen.getByText('calendar.empty_agenda')).toBeInTheDocument()
    expect(screen.getByTestId('calendar-kpi-audits')).toHaveTextContent('0')
    expect(screen.getByTestId('calendar-kpi-actions')).toHaveTextContent('0')
  })

  it('surfaces partial feed when audit or action sources fail', async () => {
    mockGetFeed.mockResolvedValue({
      data: {
        start: '2026-07-01',
        end: '2026-07-31',
        generated_at: '2026-07-16T00:00:00Z',
        total: 0,
        events: [],
        sources_ok: ['audit_runs'],
        sources_failed: ['capa_actions'],
      },
    })

    const CalendarView = (await import('../CalendarView')).default
    render(
      <MemoryRouter initialEntries={['/calendar']}>
        <Routes>
          <Route path="/calendar" element={<CalendarView />} />
        </Routes>
      </MemoryRouter>,
    )

    const banner = await screen.findByTestId('calendar-partial-feed')
    expect(banner).toBeInTheDocument()
  })

  it('shows personal-product honesty shell (not Option C)', async () => {
    const CalendarView = (await import('../CalendarView')).default
    render(
      <MemoryRouter initialEntries={['/calendar']}>
        <Routes>
          <Route path="/calendar" element={<CalendarView />} />
        </Routes>
      </MemoryRouter>,
    )

    expect(await screen.findByTestId('calendar-personal-honesty')).toBeInTheDocument()
    expect(screen.getByTestId('calendar-personal-honesty-copy')).toHaveTextContent(
      'calendar.personal_honesty.title',
    )
    expect(screen.getByTestId('calendar-personal-cap-governance_feed')).toBeInTheDocument()
    expect(screen.getByTestId('calendar-personal-cap-personal_events')).toBeInTheDocument()
    expect(screen.getByTestId('calendar-personal-cap-ics_sync')).toBeInTheDocument()
  })
})

describe('calendarView helpers', () => {
  it('countActiveByModule tallies audit runs and capa actions separately', async () => {
    const { countActiveByModule } = await import('../CalendarView')
    const counts = countActiveByModule([
      {
        id: 'a',
        title: 'A',
        type: 'audit',
        date: '2026-07-01',
        status: 'upcoming',
        source_module: 'audit_run',
        source_id: '1',
      },
      {
        id: 'b',
        title: 'B',
        type: 'deadline',
        date: '2026-07-02',
        status: 'completed',
        source_module: 'capa_action',
        source_id: '2',
      },
      {
        id: 'c',
        title: 'C',
        type: 'deadline',
        date: '2026-07-03',
        status: 'overdue',
        source_module: 'capa_action',
        source_id: '3',
      },
    ])
    expect(counts).toEqual({ audits: 1, actions: 1 })
  })

  it('labelPartialSources maps feed source keys to i18n labels', async () => {
    const { labelPartialSources } = await import('../CalendarView')
    expect(labelPartialSources(['audit_runs', 'capa_actions'], t)).toBe('audit runs, capa actions')
  })
})
