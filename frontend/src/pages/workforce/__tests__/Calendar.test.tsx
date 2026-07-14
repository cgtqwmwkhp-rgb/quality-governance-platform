import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'

import { formatScheduledDate, parseScheduledLocalDate } from '../dateUtils'
import Calendar, {
  buildCalendarEvents,
  CALENDAR_PAGE_SIZE,
  eventToneClasses,
  executeRouteForEvent,
  isListTruncated,
  startOfWeek,
  addDays,
} from '../Calendar'

const listEngineers = vi.fn()
const listAssessments = vi.fn()
const listInductions = vi.fn()
const navigate = vi.fn()
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

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return {
    ...actual,
    useNavigate: () => navigate,
  }
})

vi.mock('../../../api/client', () => ({
  workforceApi: {
    listEngineers: (...args: unknown[]) => listEngineers(...args),
    listAssessments: (...args: unknown[]) => listAssessments(...args),
    listInductions: (...args: unknown[]) => listInductions(...args),
  },
  getApiErrorMessage: (err: unknown) => (err instanceof Error ? err.message : 'load failed'),
}))

vi.mock('../../../utils/errorTracker', () => ({
  trackError: vi.fn(),
}))

vi.mock('../../../components/ui/SkeletonLoader', () => ({
  CardSkeleton: () => <div data-testid="skeleton" />,
}))

function renderCalendar() {
  return render(
    <MemoryRouter>
      <Calendar />
    </MemoryRouter>,
  )
}

const sampleAssessment = {
  id: 'a-1',
  reference_number: 'ASS-001',
  engineer_id: 7,
  scheduled_date: '2026-07-15',
  status: 'scheduled',
  template_id: 1,
  supervisor_id: 1,
  created_at: '2026-07-01T00:00:00Z',
}

const sampleInduction = {
  id: 'i-1',
  reference_number: 'IND-001',
  engineer_id: 7,
  scheduled_date: '2026-07-16',
  status: 'in_progress',
  template_id: 1,
  supervisor_id: 1,
  stage: 'day1',
  created_at: '2026-07-01T00:00:00Z',
}

describe('parseScheduledLocalDate', () => {
  it('preserves day values for date-only strings', () => {
    const parsed = parseScheduledLocalDate('2026-03-22')

    expect(parsed).not.toBeNull()
    expect(parsed?.getFullYear()).toBe(2026)
    expect(parsed?.getMonth()).toBe(2)
    expect(parsed?.getDate()).toBe(22)
  })

  it('returns null for invalid values', () => {
    expect(parseScheduledLocalDate('not-a-date')).toBeNull()
    expect(parseScheduledLocalDate()).toBeNull()
  })

  it('formats date-only strings without shifting the day', () => {
    expect(formatScheduledDate('2026-03-22')).toContain('22')
  })
})

describe('calendar helpers', () => {
  it('detects truncation when total exceeds page_size', () => {
    expect(isListTruncated(600, CALENDAR_PAGE_SIZE, 500)).toBe(true)
    expect(isListTruncated(500, CALENDAR_PAGE_SIZE, 500)).toBe(false)
    expect(isListTruncated(10, CALENDAR_PAGE_SIZE, 10)).toBe(false)
    expect(isListTruncated(undefined, CALENDAR_PAGE_SIZE, 500)).toBe(true)
    expect(isListTruncated(undefined, CALENDAR_PAGE_SIZE, 10)).toBe(false)
  })

  it('builds week ranges from Sunday', () => {
    const wed = new Date(2026, 6, 15) // Wed 15 Jul 2026
    const start = startOfWeek(wed)
    expect(start.getDay()).toBe(0)
    expect(start.getDate()).toBe(12)
    expect(addDays(start, 6).getDate()).toBe(18)
  })

  it('maps execute routes by type', () => {
    expect(executeRouteForEvent('assessment', 'a-1')).toBe('/workforce/assessments/a-1/execute')
    expect(executeRouteForEvent('induction', 'i-1')).toBe('/workforce/training/i-1/execute')
  })

  it('colours by type, status, and overdue', () => {
    expect(eventToneClasses({ type: 'assessment', status: 'scheduled', overdue: false })).toContain(
      'warning',
    )
    expect(eventToneClasses({ type: 'induction', status: 'scheduled', overdue: false })).toContain(
      'primary',
    )
    expect(eventToneClasses({ type: 'assessment', status: 'completed', overdue: false })).toContain(
      'success',
    )
    expect(eventToneClasses({ type: 'assessment', status: 'scheduled', overdue: true })).toContain(
      'destructive',
    )
  })

  it('builds events in range with engineer names', () => {
    const events = buildCalendarEvents(
      [
        { ...sampleAssessment, type: 'assessment' },
        { ...sampleInduction, type: 'induction' },
        {
          id: 'out',
          reference_number: 'OUT',
          engineer_id: 1,
          scheduled_date: '2026-08-01',
          status: 'scheduled',
          type: 'assessment',
        },
      ],
      { 7: 'E-007' },
      new Date(2026, 6, 1),
      new Date(2026, 6, 31),
      new Date(2026, 6, 14),
    )
    expect(events).toHaveLength(2)
    expect(events[0].title).toContain('E-007')
    expect(events[0].referenceNumber).toBe('ASS-001')
  })
})

describe('Calendar page', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    // Anchor "today" so month view shows July 2026 fixtures — use real July by setting system?
    // Instead schedule on current month dynamically.
    const now = new Date()
    const y = now.getFullYear()
    const m = String(now.getMonth() + 1).padStart(2, '0')
    const dayA = String(Math.min(15, new Date(y, now.getMonth() + 1, 0).getDate())).padStart(2, '0')
    const dayB = String(Math.min(16, new Date(y, now.getMonth() + 1, 0).getDate())).padStart(2, '0')

    listEngineers.mockResolvedValue({
      data: { items: [{ id: 7, employee_number: 'E-007' }], total: 1 },
    })
    listAssessments.mockResolvedValue({
      data: {
        items: [
          {
            ...sampleAssessment,
            scheduled_date: `${y}-${m}-${dayA}`,
          },
        ],
        total: 1,
      },
    })
    listInductions.mockResolvedValue({
      data: {
        items: [
          {
            ...sampleInduction,
            scheduled_date: `${y}-${m}-${dayB}`,
          },
        ],
        total: 1,
      },
    })
  })

  it('renders month view and switches to week and list', async () => {
    const user = userEvent.setup()
    renderCalendar()

    expect(await screen.findByTestId('workforce-calendar')).toBeInTheDocument()
    expect(screen.getByTestId('calendar-month-view')).toBeInTheDocument()
    expect(await screen.findByText(/ASS-001/)).toBeInTheDocument()

    await user.click(screen.getByTestId('calendar-view-week'))
    expect(await screen.findByTestId('calendar-week-view')).toBeInTheDocument()

    await user.click(screen.getByTestId('calendar-view-list'))
    expect(await screen.findByTestId('calendar-list-view')).toBeInTheDocument()
    expect(screen.getByText(/ASS-001/)).toBeInTheDocument()
    expect(screen.getByText(/IND-001/)).toBeInTheDocument()
  })

  it('navigates to execute route on event click', async () => {
    const user = userEvent.setup()
    renderCalendar()

    const eventBtn = await screen.findByText(/ASS-001/)
    await user.click(eventBtn)
    expect(navigate).toHaveBeenCalledWith('/workforce/assessments/a-1/execute')
  })

  it('surfaces truncation when assessments total exceeds page_size', async () => {
    listAssessments.mockResolvedValue({
      data: {
        items: [{ ...sampleAssessment, scheduled_date: new Date().toISOString().slice(0, 10) }],
        total: CALENDAR_PAGE_SIZE + 20,
      },
    })

    renderCalendar()

    const notice = await screen.findByTestId('calendar-truncation-notice')
    expect(notice).toHaveTextContent(/Assessments truncated/)
    expect(notice).toHaveTextContent(String(CALENDAR_PAGE_SIZE + 20))
  })

  it('surfaces engineer-map failure instead of swallowing', async () => {
    listEngineers.mockRejectedValue(new Error('engineers down'))

    renderCalendar()

    const warn = await screen.findByTestId('calendar-engineer-map-warning')
    expect(warn).toHaveTextContent(/Engineer names unavailable/)
    expect(warn).toHaveTextContent(/engineers down/)

    // Events still render with id fallback
    await waitFor(() => {
      expect(screen.getAllByText(/ASS-001/).length).toBeGreaterThan(0)
    })
    expect(screen.getAllByText(/#7/).length).toBeGreaterThan(0)
  })

  it('list view shows status chips coloured by type', async () => {
    const user = userEvent.setup()
    renderCalendar()

    await user.click(await screen.findByTestId('calendar-view-list'))
    const list = await screen.findByTestId('calendar-list-view')
    const assessRow = within(list)
      .getByText(/ASS-001/)
      .closest('button')
    expect(assessRow).toHaveAttribute('data-type', 'assessment')
    expect(assessRow).toHaveAttribute('data-status', 'scheduled')
  })
})
