import { useState, useEffect, useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import { trackError } from '../../utils/errorTracker'
import {
  ChevronLeft,
  ChevronRight,
  AlertTriangle,
  GraduationCap,
  CalendarDays,
  LayoutGrid,
  List,
} from 'lucide-react'
import { CardSkeleton } from '../../components/ui/SkeletonLoader'
import { useNavigate } from 'react-router-dom'
import { workforceApi, getApiErrorMessage } from '../../api/client'
import { cn } from '../../helpers/utils'
import { parseScheduledLocalDate } from './dateUtils'

const DAY_KEYS = ['sun', 'mon', 'tue', 'wed', 'thu', 'fri', 'sat'] as const

/** Page size used for calendar list fetches — surface honesty when total exceeds this. */
export const CALENDAR_PAGE_SIZE = 500

export type CalendarViewMode = 'month' | 'week' | 'list'

export interface CalendarEvent {
  date: number
  fullDate: Date
  type: 'assessment' | 'induction'
  status: string
  title: string
  overdue: boolean
  id: string
  referenceNumber: string
}

interface ScheduledWorkItem {
  id: string
  reference_number: string
  engineer_id: number
  scheduled_date?: string
  status: string
  type: 'assessment' | 'induction'
}

export function isListTruncated(
  total: number | undefined,
  pageSize: number,
  itemCount: number,
): boolean {
  if (typeof total === 'number') return total > pageSize
  // Fallback when API omits total but returned a full page (possible truncation).
  return itemCount >= pageSize
}

export function startOfWeek(date: Date): Date {
  const d = new Date(date.getFullYear(), date.getMonth(), date.getDate())
  d.setDate(d.getDate() - d.getDay())
  return d
}

export function addDays(date: Date, days: number): Date {
  const d = new Date(date.getFullYear(), date.getMonth(), date.getDate())
  d.setDate(d.getDate() + days)
  return d
}

export function executeRouteForEvent(type: 'assessment' | 'induction', id: string): string {
  return type === 'assessment'
    ? `/workforce/assessments/${id}/execute`
    : `/workforce/training/${id}/execute`
}

export function eventToneClasses(ev: Pick<CalendarEvent, 'type' | 'status' | 'overdue'>): string {
  if (ev.overdue) {
    return 'border-destructive/50 bg-destructive/10 text-destructive-foreground hover:bg-destructive/20'
  }
  if (ev.status === 'completed') {
    return 'border-success/40 bg-success/10 text-success-foreground hover:bg-success/20'
  }
  if (ev.status === 'in_progress' || ev.status === 'pending_debrief') {
    return 'border-warning/50 bg-warning/15 text-warning-foreground hover:bg-warning/25'
  }
  if (ev.status === 'cancelled') {
    return 'border-muted bg-muted/40 text-muted-foreground hover:bg-muted/60 line-through'
  }
  // Scheduled / draft / default — colour by type
  return ev.type === 'assessment'
    ? 'border-warning/50 bg-warning/10 text-warning-foreground hover:bg-warning/20'
    : 'border-primary/30 bg-primary/10 text-primary-foreground hover:bg-primary/20'
}

export function buildCalendarEvents(
  items: ScheduledWorkItem[],
  engineerMap: Record<number, string>,
  rangeStart: Date,
  rangeEnd: Date,
  today: Date = new Date(),
): CalendarEvent[] {
  const dayStart = new Date(today.getFullYear(), today.getMonth(), today.getDate())

  return items
    .filter((item) => {
      const date = parseScheduledLocalDate(item.scheduled_date)
      if (!date) return false
      return date >= rangeStart && date <= rangeEnd
    })
    .map<CalendarEvent>((item) => {
      const date = parseScheduledLocalDate(item.scheduled_date) ?? new Date()
      const engineerName = engineerMap[item.engineer_id] ?? `#${item.engineer_id}`
      return {
        date: date.getDate(),
        fullDate: date,
        type: item.type,
        status: item.status,
        title: `${item.reference_number} - ${engineerName}`,
        overdue: date < dayStart && item.status !== 'completed' && item.status !== 'cancelled',
        id: item.id,
        referenceNumber: item.reference_number,
      }
    })
    .sort((a, b) => a.fullDate.getTime() - b.fullDate.getTime())
}

export default function Calendar() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [viewMode, setViewMode] = useState<CalendarViewMode>('month')
  const [year, setYear] = useState(() => new Date().getFullYear())
  const [month, setMonth] = useState(() => new Date().getMonth())
  const [weekStart, setWeekStart] = useState(() => startOfWeek(new Date()))
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [truncationNotice, setTruncationNotice] = useState<string | null>(null)
  const [engineerMapWarning, setEngineerMapWarning] = useState<string | null>(null)

  const [engineerMap, setEngineerMap] = useState<Record<number, string>>({})
  const [scheduledItems, setScheduledItems] = useState<ScheduledWorkItem[]>([])

  useEffect(() => {
    workforceApi
      .listEngineers({ page: '1', page_size: String(CALENDAR_PAGE_SIZE) })
      .then((res) => {
        const items = res.data?.items || []
        const total = res.data?.total
        const map: Record<number, string> = {}
        for (const e of items) {
          map[e.id] = e.employee_number || e.job_title || `#${e.id}`
        }
        setEngineerMap(map)
        if (isListTruncated(total, CALENDAR_PAGE_SIZE, items.length)) {
          setEngineerMapWarning(
            t('workforce.calendar.engineers_truncated', {
              defaultValue:
                'Engineer names may be incomplete — showing {{shown}} of {{total}} engineers.',
              shown: items.length,
              total: typeof total === 'number' ? total : `${items.length}+`,
            }),
          )
        } else {
          setEngineerMapWarning(null)
        }
      })
      .catch((err) => {
        trackError(err, { component: 'Calendar', action: 'listEngineers' })
        setEngineerMap({})
        setEngineerMapWarning(
          t('workforce.calendar.engineers_unavailable', {
            defaultValue:
              'Engineer names unavailable — events show engineer IDs only. {{detail}}',
            detail: getApiErrorMessage(err),
          }),
        )
      })
  }, [])

  useEffect(() => {
    const load = async () => {
      setLoading(true)
      setError(null)
      try {
        const [assessRes, inductRes] = await Promise.all([
          workforceApi.listAssessments({ page: '1', page_size: String(CALENDAR_PAGE_SIZE) }),
          workforceApi.listInductions({ page: '1', page_size: String(CALENDAR_PAGE_SIZE) }),
        ])
        const assessments = assessRes.data?.items || []
        const inductions = inductRes.data?.items || []
        const assessTotal = assessRes.data?.total
        const inductTotal = inductRes.data?.total

        setScheduledItems([
          ...assessments.map((assessment) => ({ ...assessment, type: 'assessment' as const })),
          ...inductions.map((induction) => ({ ...induction, type: 'induction' as const })),
        ])

        const notices: string[] = []
        if (isListTruncated(assessTotal, CALENDAR_PAGE_SIZE, assessments.length)) {
          notices.push(
            t('workforce.calendar.assessments_truncated', {
              defaultValue: 'Assessments truncated: showing {{shown}} of {{total}}.',
              shown: assessments.length,
              total: typeof assessTotal === 'number' ? assessTotal : `${assessments.length}+`,
            }),
          )
        }
        if (isListTruncated(inductTotal, CALENDAR_PAGE_SIZE, inductions.length)) {
          notices.push(
            t('workforce.calendar.inductions_truncated', {
              defaultValue: 'Inductions truncated: showing {{shown}} of {{total}}.',
              shown: inductions.length,
              total: typeof inductTotal === 'number' ? inductTotal : `${inductions.length}+`,
            }),
          )
        }
        setTruncationNotice(notices.length ? notices.join(' ') : null)
      } catch (err) {
        trackError(err, { component: 'Calendar', action: 'load' })
        setError(getApiErrorMessage(err))
        setScheduledItems([])
        setTruncationNotice(null)
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  const { rangeStart, rangeEnd } = useMemo(() => {
    if (viewMode === 'week') {
      return {
        rangeStart: weekStart,
        rangeEnd: addDays(weekStart, 6),
      }
    }
    // month + list agenda use the selected calendar month
    return {
      rangeStart: new Date(year, month, 1),
      rangeEnd: new Date(year, month + 1, 0),
    }
  }, [viewMode, weekStart, year, month])

  const events = useMemo(
    () => buildCalendarEvents(scheduledItems, engineerMap, rangeStart, rangeEnd),
    [engineerMap, rangeEnd, rangeStart, scheduledItems],
  )

  const firstDay = new Date(year, month, 1).getDay()
  const daysInMonth = new Date(year, month + 1, 0).getDate()
  const days: (number | null)[] = Array(firstDay).fill(null)
  for (let d = 1; d <= daysInMonth; d++) days.push(d)

  const monthName = new Date(year, month).toLocaleString('default', { month: 'long' })
  const weekEnd = addDays(weekStart, 6)
  const weekLabel = `${weekStart.toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
  })} – ${weekEnd.toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })}`

  const getEventsForDay = (day: number) => events.filter((e) => e.date === day)

  const getEventsForDate = (date: Date) =>
    events.filter(
      (e) =>
        e.fullDate.getFullYear() === date.getFullYear() &&
        e.fullDate.getMonth() === date.getMonth() &&
        e.fullDate.getDate() === date.getDate(),
    )

  const navigateEvent = (ev: CalendarEvent) => {
    navigate(executeRouteForEvent(ev.type, ev.id))
  }

  const shiftMonth = (delta: number) => {
    const next = new Date(year, month + delta, 1)
    setYear(next.getFullYear())
    setMonth(next.getMonth())
    setWeekStart(startOfWeek(next))
  }

  const shiftWeek = (delta: number) => {
    const next = addDays(weekStart, delta * 7)
    setWeekStart(next)
    setYear(next.getFullYear())
    setMonth(next.getMonth())
  }

  const setMode = (mode: CalendarViewMode) => {
    if (mode === 'week') {
      setWeekStart(startOfWeek(new Date(year, month, Math.min(new Date().getDate(), daysInMonth))))
    }
    setViewMode(mode)
  }

  const weekDays = useMemo(
    () => Array.from({ length: 7 }, (_, i) => addDays(weekStart, i)),
    [weekStart],
  )

  const viewButtons: { mode: CalendarViewMode; icon: typeof LayoutGrid; label: string }[] = [
    {
      mode: 'month',
      icon: LayoutGrid,
      label: t('workforce.calendar.view_month', { defaultValue: 'Month' }),
    },
    {
      mode: 'week',
      icon: CalendarDays,
      label: t('workforce.calendar.view_week', { defaultValue: 'Week' }),
    },
    {
      mode: 'list',
      icon: List,
      label: t('workforce.calendar.view_list', { defaultValue: 'List' }),
    },
  ]

  return (
    <div className="space-y-6" data-testid="workforce-calendar">
      {error && (
        <div className="bg-destructive/10 text-destructive p-4 rounded-lg" role="alert">
          {error}
        </div>
      )}
      {truncationNotice && (
        <div
          className="bg-warning/10 text-warning-foreground border border-warning/30 p-4 rounded-lg text-sm"
          role="status"
          data-testid="calendar-truncation-notice"
        >
          <AlertTriangle className="w-4 h-4 inline mr-2" />
          {truncationNotice}
        </div>
      )}
      {engineerMapWarning && (
        <div
          className="bg-muted text-muted-foreground border border-border p-4 rounded-lg text-sm"
          role="status"
          data-testid="calendar-engineer-map-warning"
        >
          <AlertTriangle className="w-4 h-4 inline mr-2" />
          {engineerMapWarning}
        </div>
      )}
      <div>
        <h1 className="text-2xl font-bold text-foreground">{t('workforce.calendar.title')}</h1>
        <p className="text-muted-foreground mt-1">{t('workforce.calendar.subtitle')}</p>
      </div>

      {loading && <CardSkeleton count={3} />}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => (viewMode === 'week' ? shiftWeek(-1) : shiftMonth(-1))}
            className="p-2 rounded-lg border border-border bg-card text-foreground hover:bg-muted transition-colors"
            aria-label={t('workforce.calendar.prev', { defaultValue: 'Previous' })}
          >
            <ChevronLeft className="w-5 h-5" />
          </button>
          <h2
            className="text-xl font-semibold text-foreground min-w-[200px] text-center"
            data-testid="calendar-period-label"
          >
            {viewMode === 'week' ? weekLabel : `${monthName} ${year}`}
          </h2>
          <button
            type="button"
            onClick={() => (viewMode === 'week' ? shiftWeek(1) : shiftMonth(1))}
            className="p-2 rounded-lg border border-border bg-card text-foreground hover:bg-muted transition-colors"
            aria-label={t('workforce.calendar.next', { defaultValue: 'Next' })}
          >
            <ChevronRight className="w-5 h-5" />
          </button>
        </div>

        <div className="flex flex-wrap items-center gap-4">
          <div
            className="flex bg-muted/40 rounded-lg p-1 border border-border"
            role="tablist"
            aria-label={t('workforce.calendar.views', { defaultValue: 'Calendar views' })}
          >
            {viewButtons.map(({ mode, icon: Icon, label }) => (
              <button
                key={mode}
                type="button"
                role="tab"
                aria-selected={viewMode === mode}
                data-testid={`calendar-view-${mode}`}
                onClick={() => setMode(mode)}
                className={cn(
                  'flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm transition-colors',
                  viewMode === mode
                    ? 'bg-card text-foreground shadow-sm'
                    : 'text-muted-foreground hover:text-foreground',
                )}
              >
                <Icon className="w-4 h-4" />
                {label}
              </button>
            ))}
          </div>
          <div className="flex items-center gap-4 text-sm">
            <span className="flex items-center gap-2 text-muted-foreground">
              <AlertTriangle className="w-4 h-4 text-warning" />
              {t('workforce.calendar.assessment')}
            </span>
            <span className="flex items-center gap-2 text-muted-foreground">
              <GraduationCap className="w-4 h-4 text-primary" />
              {t('workforce.calendar.induction')}
            </span>
          </div>
        </div>
      </div>

      {viewMode === 'month' && (
        <div className="rounded-xl border border-border bg-card overflow-hidden" data-testid="calendar-month-view">
          <div className="grid grid-cols-7 border-b border-border bg-muted/30">
            {DAY_KEYS.map((key) => (
              <div
                key={key}
                className="py-3 px-2 text-center text-xs font-medium text-muted-foreground"
              >
                {t(`workforce.calendar.${key}`)}
              </div>
            ))}
          </div>
          <div className="grid grid-cols-7">
            {days.map((day, i) => (
              <div
                key={i}
                className={cn(
                  'min-h-[100px] p-2 border-b border-r border-border/50',
                  (i + 1) % 7 === 0 && 'border-r-0',
                )}
              >
                {day !== null ? (
                  <>
                    <div className="text-sm font-medium text-foreground mb-2">{day}</div>
                    <div className="space-y-1">
                      {getEventsForDay(day).map((ev) => (
                        <button
                          key={ev.id}
                          type="button"
                          onClick={() => navigateEvent(ev)}
                          className={cn(
                            'w-full text-left text-xs px-2 py-1.5 rounded border truncate block',
                            eventToneClasses(ev),
                          )}
                          title={`${ev.title} (${ev.status})`}
                          data-status={ev.status}
                          data-type={ev.type}
                        >
                          {ev.overdue && <AlertTriangle className="w-3 h-3 inline mr-1" />}
                          {ev.title}
                        </button>
                      ))}
                    </div>
                  </>
                ) : null}
              </div>
            ))}
          </div>
        </div>
      )}

      {viewMode === 'week' && (
        <div className="rounded-xl border border-border bg-card overflow-hidden" data-testid="calendar-week-view">
          <div className="grid grid-cols-1 sm:grid-cols-7 divide-y sm:divide-y-0 sm:divide-x divide-border">
            {weekDays.map((date) => {
              const dayEvents = getEventsForDate(date)
              const now = new Date()
              const isToday =
                date.getFullYear() === now.getFullYear() &&
                date.getMonth() === now.getMonth() &&
                date.getDate() === now.getDate()
              return (
                <div
                  key={date.toISOString()}
                  className={cn('min-h-[140px] p-3', isToday && 'bg-primary/5')}
                  data-testid={`calendar-week-day-${date.getDate()}`}
                >
                  <div className="flex items-baseline justify-between mb-2">
                    <span className="text-xs font-medium text-muted-foreground uppercase">
                      {t(`workforce.calendar.${DAY_KEYS[date.getDay()]}`)}
                    </span>
                    <span
                      className={cn(
                        'text-sm font-semibold',
                        isToday ? 'text-primary' : 'text-foreground',
                      )}
                    >
                      {date.getDate()}
                    </span>
                  </div>
                  <div className="space-y-1">
                    {dayEvents.length === 0 && (
                      <p className="text-xs text-muted-foreground">
                        {t('workforce.calendar.no_events', { defaultValue: 'No events' })}
                      </p>
                    )}
                    {dayEvents.map((ev) => (
                      <button
                        key={ev.id}
                        type="button"
                        onClick={() => navigateEvent(ev)}
                        className={cn(
                          'w-full text-left text-xs px-2 py-1.5 rounded border truncate block',
                          eventToneClasses(ev),
                        )}
                        title={`${ev.title} (${ev.status})`}
                        data-status={ev.status}
                        data-type={ev.type}
                      >
                        {ev.overdue && <AlertTriangle className="w-3 h-3 inline mr-1" />}
                        {ev.title}
                      </button>
                    ))}
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {viewMode === 'list' && (
        <div
          className="rounded-xl border border-border bg-card overflow-hidden divide-y divide-border"
          data-testid="calendar-list-view"
        >
          {events.length === 0 && !loading && (
            <p className="p-6 text-sm text-muted-foreground" data-testid="calendar-list-empty">
              {t('workforce.calendar.no_events_month', {
                defaultValue: 'No scheduled activities this month.',
              })}
            </p>
          )}
          {events.map((ev) => (
            <button
              key={ev.id}
              type="button"
              onClick={() => navigateEvent(ev)}
              className={cn(
                'w-full text-left px-4 py-3 flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-4 hover:bg-muted/40 transition-colors border-l-4',
                ev.type === 'assessment' ? 'border-l-warning' : 'border-l-primary',
                ev.overdue && 'border-l-destructive',
                ev.status === 'completed' && 'border-l-success',
              )}
              data-status={ev.status}
              data-type={ev.type}
            >
              <div className="min-w-[100px] text-sm text-muted-foreground">
                {ev.fullDate.toLocaleDateString(undefined, {
                  weekday: 'short',
                  month: 'short',
                  day: 'numeric',
                })}
              </div>
              <div className="flex-1 min-w-0">
                <div className="font-medium text-foreground truncate">{ev.title}</div>
                <div className="flex flex-wrap gap-2 mt-1 text-xs">
                  <span
                    className={cn(
                      'px-2 py-0.5 rounded border',
                      eventToneClasses(ev),
                    )}
                  >
                    {ev.type === 'assessment'
                      ? t('workforce.calendar.assessment')
                      : t('workforce.calendar.induction')}
                  </span>
                  <span className="px-2 py-0.5 rounded border border-border text-muted-foreground capitalize">
                    {ev.status.replace(/_/g, ' ')}
                  </span>
                  {ev.overdue && (
                    <span className="px-2 py-0.5 rounded border border-destructive/40 text-destructive">
                      {t('workforce.calendar.overdue', { defaultValue: 'Overdue' })}
                    </span>
                  )}
                </div>
              </div>
              <ChevronRight className="w-4 h-4 text-muted-foreground shrink-0 hidden sm:block" />
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
