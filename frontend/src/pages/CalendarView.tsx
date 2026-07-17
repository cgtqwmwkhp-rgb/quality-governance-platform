import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import {
  Calendar as CalendarIcon,
  ChevronLeft,
  ChevronRight,
  Plus,
  Clock,
  AlertTriangle,
  Filter,
  List,
  Grid3X3,
  Columns3,
  Loader2,
  ExternalLink,
  X,
} from 'lucide-react'
import {
  calendarApi,
  getApiErrorMessage,
  type CalendarFeedEvent,
  type CalendarEventType,
} from '../api/client'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { Badge } from '../components/ui/Badge'
import { cn } from '../helpers/utils'
import { toast } from '../contexts/ToastContext'

type ViewMode = 'month' | 'week' | 'agenda'
type EventType = CalendarEventType

export const AUDIT_SOURCE_MODULES = new Set(['audit_run', 'scheduled_audit'])
export const ACTION_SOURCE_MODULES = new Set(['capa_action'])

export function countActiveByModule(events: CalendarFeedEvent[]) {
  const active = events.filter((e) => e.status !== 'completed')
  return {
    audits: active.filter((e) => AUDIT_SOURCE_MODULES.has(e.source_module)).length,
    actions: active.filter((e) => ACTION_SOURCE_MODULES.has(e.source_module)).length,
  }
}

export function labelPartialSources(
  sources: string[],
  t: (key: string, options?: { defaultValue?: string }) => string,
) {
  return sources
    .map((s) => t(`calendar.source_label.${s}`, { defaultValue: s.replace(/_/g, ' ') }))
    .join(', ')
}

const ALL_TYPES: EventType[] = ['audit', 'deadline', 'review', 'training', 'meeting']

const TYPE_CHIP: Record<EventType, { chip: string; dot: string; border: string }> = {
  audit: {
    chip: 'bg-info/15 text-info border-info/30',
    dot: 'bg-info',
    border: 'border-l-info',
  },
  review: {
    chip: 'bg-purple-500/15 text-purple-700 dark:text-purple-300 border-purple-500/30',
    dot: 'bg-purple-500',
    border: 'border-l-purple-500',
  },
  deadline: {
    chip: 'bg-destructive/15 text-destructive border-destructive/30',
    dot: 'bg-destructive',
    border: 'border-l-destructive',
  },
  meeting: {
    chip: 'bg-success/15 text-success border-success/30',
    dot: 'bg-success',
    border: 'border-l-success',
  },
  training: {
    chip: 'bg-warning/15 text-warning border-warning/30',
    dot: 'bg-warning',
    border: 'border-l-warning',
  },
}

function startOfMonth(d: Date) {
  return new Date(d.getFullYear(), d.getMonth(), 1)
}

function endOfMonth(d: Date) {
  return new Date(d.getFullYear(), d.getMonth() + 1, 0)
}

function startOfWeek(d: Date) {
  const x = new Date(d.getFullYear(), d.getMonth(), d.getDate())
  x.setDate(x.getDate() - x.getDay())
  return x
}

function addDays(d: Date, n: number) {
  const x = new Date(d.getFullYear(), d.getMonth(), d.getDate())
  x.setDate(x.getDate() + n)
  return x
}

function toISODate(d: Date) {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

function parseISODate(s: string) {
  const [y, m, d] = s.split('-').map(Number)
  return new Date(y, (m || 1) - 1, d || 1)
}

function sameDay(a: Date, b: Date) {
  return (
    a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate()
  )
}

function EventChip({
  event,
  compact,
  typeLabel,
  statusLabel,
}: {
  event: CalendarFeedEvent
  compact?: boolean
  typeLabel: string
  statusLabel: string
}) {
  const style = TYPE_CHIP[event.type] ?? TYPE_CHIP.deadline
  const tip = [
    event.title,
    `${typeLabel} · ${statusLabel}`,
    event.owner ? `Owner: ${event.owner}` : null,
    event.date,
    event.description || null,
  ]
    .filter(Boolean)
    .join('\n')

  return (
    <Link
      to={event.href || '#'}
      title={tip}
      onClick={(e) => e.stopPropagation()}
      className={cn(
        'block truncate rounded border px-1.5 py-0.5 text-[10px] font-medium leading-tight transition-colors hover:brightness-110',
        style.chip,
        compact && 'max-w-full',
      )}
      data-testid={`calendar-chip-${event.id}`}
    >
      {event.title}
    </Link>
  )
}

export default function CalendarView() {
  const { t } = useTranslation()
  const [searchParams, setSearchParams] = useSearchParams()
  const today = useMemo(() => new Date(), [])
  const [cursor, setCursor] = useState(() => startOfMonth(new Date()))
  const viewMode = (searchParams.get('view') as ViewMode | null) || 'month'
  const typesParam = searchParams.get('types') || ''
  const selectedTypes = useMemo(() => {
    const parts = typesParam
      .split(',')
      .map((t) => t.trim().toLowerCase())
      .filter((t): t is EventType => ALL_TYPES.includes(t as EventType))
    return parts
  }, [typesParam])
  const selectedDayParam = searchParams.get('day')
  const selectedDay = selectedDayParam ? parseISODate(selectedDayParam) : null

  const [showFilters, setShowFilters] = useState(selectedTypes.length > 0)
  const [showAdd, setShowAdd] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [partial, setPartial] = useState<string[]>([])
  const [events, setEvents] = useState<CalendarFeedEvent[]>([])

  const setQuery = useCallback(
    (patch: Record<string, string | null>) => {
      const next = new URLSearchParams(searchParams)
      Object.entries(patch).forEach(([k, v]) => {
        if (v == null || v === '' || (k === 'view' && v === 'month')) next.delete(k)
        else next.set(k, v)
      })
      setSearchParams(next, { replace: true })
    },
    [searchParams, setSearchParams],
  )

  const range = useMemo(() => {
    if (viewMode === 'week') {
      const start = startOfWeek(selectedDay ?? cursor)
      return { start: toISODate(start), end: toISODate(addDays(start, 6)) }
    }
    if (viewMode === 'agenda') {
      const start = selectedDay ?? today
      return { start: toISODate(start), end: toISODate(addDays(start, 60)) }
    }
    const start = startOfMonth(cursor)
    const end = endOfMonth(cursor)
    // Include leading/trailing week padding days for month grid
    return {
      start: toISODate(startOfWeek(start)),
      end: toISODate(addDays(startOfWeek(end), 6)),
    }
  }, [viewMode, cursor, selectedDay, today])

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await calendarApi.getFeed({
        start: range.start,
        end: range.end,
        types: selectedTypes.length ? selectedTypes : undefined,
      })
      setEvents(res.data.events ?? [])
      setPartial(res.data.sources_failed ?? [])
    } catch (err) {
      setEvents([])
      setError(getApiErrorMessage(err))
      toast.error(getApiErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }, [range.start, range.end, selectedTypes])

  useEffect(() => {
    void load()
  }, [load])

  const eventsByDate = useMemo(() => {
    const map = new Map<string, CalendarFeedEvent[]>()
    for (const ev of events) {
      const list = map.get(ev.date) ?? []
      list.push(ev)
      map.set(ev.date, list)
    }
    return map
  }, [events])

  const monthCells = useMemo(() => {
    const first = startOfMonth(cursor)
    const start = startOfWeek(first)
    return Array.from({ length: 42 }, (_, i) => addDays(start, i))
  }, [cursor])

  const weekDays = useMemo(() => {
    const start = startOfWeek(selectedDay ?? cursor)
    return Array.from({ length: 7 }, (_, i) => addDays(start, i))
  }, [selectedDay, cursor])

  const dayEvents = selectedDay
    ? eventsByDate.get(toISODate(selectedDay)) ?? []
    : []

  const upcoming = useMemo(() => {
    const todayIso = toISODate(today)
    return [...events]
      .filter((e) => e.status !== 'completed' && e.date >= todayIso)
      .slice(0, 8)
  }, [events, today])

  const feedCounts = useMemo(() => countActiveByModule(events), [events])

  const typeLabel = useCallback(
    (type: EventType) => t(`calendar.type.${type}`, { defaultValue: type }),
    [t],
  )

  const statusLabel = useCallback(
    (status: string) =>
      t(`calendar.status.${status}`, { defaultValue: status.replace(/_/g, ' ') }),
    [t],
  )

  const sourceModuleLabel = useCallback(
    (sourceModule: string) => {
      if (AUDIT_SOURCE_MODULES.has(sourceModule)) return t('calendar.source_audit')
      if (ACTION_SOURCE_MODULES.has(sourceModule)) return t('calendar.source_action')
      return t(`calendar.source_label.${sourceModule}`, {
        defaultValue: sourceModule.replace(/_/g, ' '),
      })
    },
    [t],
  )

  const toggleType = (type: EventType) => {
    const next = new Set(selectedTypes)
    if (next.has(type)) next.delete(type)
    else next.add(type)
    const list = ALL_TYPES.filter((t) => next.has(t))
    setQuery({ types: list.length ? list.join(',') : null })
  }

  const monthNames = [
    'January',
    'February',
    'March',
    'April',
    'May',
    'June',
    'July',
    'August',
    'September',
    'October',
    'November',
    'December',
  ]
  const dayNames = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']

  return (
    <div className="space-y-6 animate-fade-in" data-testid="governance-calendar">
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-foreground flex items-center gap-3">
            <div className="p-2 bg-primary/10 rounded-xl">
              <CalendarIcon className="w-8 h-8 text-primary" />
            </div>
            {t('calendar.title')}
          </h1>
          <p className="text-muted-foreground mt-1">{t('calendar.subtitle')}</p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <div className="flex bg-surface rounded-lg p-1 border border-border">
            {(
              [
                ['month', Grid3X3, t('calendar.month')],
                ['week', Columns3, t('calendar.week')],
                ['agenda', List, t('calendar.agenda')],
              ] as const
            ).map(([mode, Icon, label]) => (
              <button
                key={mode}
                type="button"
                title={label}
                onClick={() => setQuery({ view: mode === 'month' ? 'month' : mode })}
                className={cn(
                  'p-2 rounded-md transition-all',
                  viewMode === mode
                    ? 'bg-primary text-primary-foreground'
                    : 'text-muted-foreground hover:text-foreground',
                )}
              >
                <Icon className="w-5 h-5" />
              </button>
            ))}
          </div>

          <Button
            variant={showFilters ? 'default' : 'outline'}
            size="sm"
            onClick={() => setShowFilters((v) => !v)}
            aria-label={t('calendar.filters')}
          >
            <Filter className="w-4 h-4" />
          </Button>

          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              setCursor(startOfMonth(today))
              setQuery({ day: toISODate(today) })
            }}
          >
            {t('calendar.today')}
          </Button>

          <div className="relative">
            <Button onClick={() => setShowAdd((v) => !v)} data-testid="calendar-add-event">
              <Plus className="w-4 h-4" />
              {t('calendar.add_event')}
            </Button>
            {showAdd && (
              <Card className="absolute right-0 mt-2 z-20 w-56 p-2 shadow-lg border border-border">
                <p className="text-xs text-muted-foreground px-2 py-1">
                  {t('calendar.create_from_source')}
                </p>
                <Link
                  to="/audits"
                  className="block rounded-md px-3 py-2 text-sm hover:bg-accent"
                  onClick={() => setShowAdd(false)}
                >
                  {t('calendar.schedule_audit')}
                </Link>
                <Link
                  to="/actions"
                  className="block rounded-md px-3 py-2 text-sm hover:bg-accent"
                  onClick={() => setShowAdd(false)}
                >
                  {t('calendar.create_action')}
                </Link>
              </Card>
            )}
          </div>
        </div>
      </div>

      <div
        className="grid grid-cols-1 sm:grid-cols-2 gap-3"
        data-testid="calendar-source-kpis"
      >
        <Card className="p-4 flex items-center justify-between gap-3">
          <div>
            <p className="text-sm font-medium text-foreground">{t('calendar.kpi_audits')}</p>
            <p className="text-xs text-muted-foreground mt-0.5">{t('calendar.kpi_audits_hint')}</p>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-2xl font-bold text-info" data-testid="calendar-kpi-audits">
              {feedCounts.audits}
            </span>
            <Button asChild size="sm" variant="outline">
              <Link to="/audits">{t('calendar.schedule_audit')}</Link>
            </Button>
          </div>
        </Card>
        <Card className="p-4 flex items-center justify-between gap-3">
          <div>
            <p className="text-sm font-medium text-foreground">{t('calendar.kpi_actions')}</p>
            <p className="text-xs text-muted-foreground mt-0.5">{t('calendar.kpi_actions_hint')}</p>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-2xl font-bold text-destructive" data-testid="calendar-kpi-actions">
              {feedCounts.actions}
            </span>
            <Button asChild size="sm" variant="outline">
              <Link to="/actions">{t('calendar.create_action')}</Link>
            </Button>
          </div>
        </Card>
      </div>

      {showFilters && (
        <Card className="p-4" data-testid="calendar-type-filters">
          <div className="flex flex-wrap gap-2">
            {ALL_TYPES.map((type) => {
              const active = selectedTypes.length === 0 || selectedTypes.includes(type)
              return (
                <button
                  key={type}
                  type="button"
                  onClick={() => toggleType(type)}
                  className={cn(
                    'inline-flex items-center gap-2 rounded-full border px-3 py-1 text-sm transition-colors',
                    active ? TYPE_CHIP[type].chip : 'border-border text-muted-foreground opacity-60',
                  )}
                >
                  <span className={cn('h-2 w-2 rounded-full', TYPE_CHIP[type].dot)} />
                  {typeLabel(type)}
                </button>
              )
            })}
            {selectedTypes.length > 0 && (
              <Button variant="ghost" size="sm" onClick={() => setQuery({ types: null })}>
                {t('calendar.clear_filters')}
              </Button>
            )}
          </div>
        </Card>
      )}

      {error && (
        <div role="alert" className="rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          {error}
        </div>
      )}
      {partial.length > 0 && !error && (
        <div
          role="status"
          className="rounded-lg border border-warning/30 bg-warning/10 px-4 py-3 text-sm"
          data-testid="calendar-partial-feed"
        >
          {t('calendar.partial_feed', { sources: labelPartialSources(partial, t) })}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        <Card className="lg:col-span-3 p-6">
          <div className="flex items-center justify-between mb-6">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                if (viewMode === 'week') {
                  const base = selectedDay ?? cursor
                  const prev = addDays(base, -7)
                  setCursor(startOfMonth(prev))
                  setQuery({ day: toISODate(prev) })
                } else {
                  setCursor(new Date(cursor.getFullYear(), cursor.getMonth() - 1, 1))
                }
              }}
            >
              <ChevronLeft className="w-5 h-5" />
            </Button>
            <h2 className="text-xl font-semibold text-foreground">
              {viewMode === 'week'
                ? t('calendar.week_of', { date: toISODate(weekDays[0]!) })
                : viewMode === 'agenda'
                  ? t('calendar.agenda')
                  : `${monthNames[cursor.getMonth()]} ${cursor.getFullYear()}`}
            </h2>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                if (viewMode === 'week') {
                  const base = selectedDay ?? cursor
                  const next = addDays(base, 7)
                  setCursor(startOfMonth(next))
                  setQuery({ day: toISODate(next) })
                } else {
                  setCursor(new Date(cursor.getFullYear(), cursor.getMonth() + 1, 1))
                }
              }}
            >
              <ChevronRight className="w-5 h-5" />
            </Button>
          </div>

          {loading ? (
            <div className="flex h-64 items-center justify-center">
              <Loader2 className="w-8 h-8 animate-spin text-primary" />
            </div>
          ) : viewMode === 'agenda' ? (
            <div className="space-y-3" data-testid="calendar-agenda">
              {events.length === 0 ? (
                <div
                  className="py-16 text-center text-muted-foreground text-sm space-y-3"
                  data-testid="calendar-empty-agenda"
                >
                  <p>{t('calendar.empty_agenda')}</p>
                  <div className="flex justify-center gap-2">
                    <Button asChild size="sm">
                      <Link to="/audits">{t('calendar.schedule_audit')}</Link>
                    </Button>
                    <Button asChild size="sm" variant="outline">
                      <Link to="/actions">{t('calendar.create_action')}</Link>
                    </Button>
                  </div>
                </div>
              ) : (
                events.map((event) => (
                  <Card
                    key={event.id}
                    className={cn('p-4 border-l-4', TYPE_CHIP[event.type]?.border)}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <div className="flex flex-wrap gap-2 mb-1">
                          <Badge variant="outline">{typeLabel(event.type)}</Badge>
                          <Badge variant="secondary">{sourceModuleLabel(event.source_module)}</Badge>
                          <Badge
                            variant={
                              event.status === 'overdue'
                                ? 'destructive'
                                : event.status === 'today'
                                  ? 'info'
                                  : 'secondary'
                            }
                          >
                            {statusLabel(event.status)}
                          </Badge>
                        </div>
                        <h3 className="font-semibold text-foreground">{event.title}</h3>
                        <p className="text-sm text-muted-foreground mt-1 flex items-center gap-2">
                          <Clock className="w-3.5 h-3.5" />
                          {event.date}
                          {event.owner ? ` · ${event.owner}` : ''}
                        </p>
                      </div>
                      {event.href && (
                        <Button asChild size="sm" variant="outline">
                          <Link to={event.href}>
                            {t('calendar.open_source')} <ExternalLink className="w-3.5 h-3.5 ml-1" />
                          </Link>
                        </Button>
                      )}
                    </div>
                  </Card>
                ))
              )}
            </div>
          ) : (
            <>
              <div className="grid grid-cols-7 gap-1 mb-2">
                {dayNames.map((day) => (
                  <div
                    key={day}
                    className="text-center text-sm font-medium text-muted-foreground py-2"
                  >
                    {day}
                  </div>
                ))}
              </div>
              <div
                className="grid grid-cols-7 gap-1"
                data-testid={viewMode === 'week' ? 'calendar-week' : 'calendar-month'}
              >
                {(viewMode === 'week' ? weekDays : monthCells).map((day) => {
                  const iso = toISODate(day)
                  const dayEv = eventsByDate.get(iso) ?? []
                  const isToday = sameDay(day, today)
                  const inMonth = day.getMonth() === cursor.getMonth()
                  const isSelected = selectedDay ? sameDay(day, selectedDay) : false
                  return (
                    <button
                      key={iso}
                      type="button"
                      onClick={() => setQuery({ day: iso })}
                      className={cn(
                        'min-h-[100px] p-2 rounded-lg text-left transition-all border',
                        'bg-surface hover:bg-accent/40',
                        !inMonth && viewMode === 'month' && 'opacity-45',
                        isToday && 'ring-2 ring-primary',
                        isSelected && 'border-primary bg-primary/5',
                        !isSelected && 'border-transparent',
                      )}
                    >
                      <span
                        className={cn(
                          'text-sm font-medium',
                          isToday ? 'text-primary' : 'text-muted-foreground',
                        )}
                      >
                        {day.getDate()}
                      </span>
                      <div className="mt-1 space-y-1">
                        {dayEv.slice(0, 3).map((event) => (
                          <EventChip
                            key={event.id}
                            event={event}
                            compact
                            typeLabel={typeLabel(event.type)}
                            statusLabel={statusLabel(event.status)}
                          />
                        ))}
                        {dayEv.length > 3 && (
                          <span className="text-[10px] text-muted-foreground pl-0.5">
                            {t('calendar.more', { count: dayEv.length - 3 })}
                          </span>
                        )}
                      </div>
                    </button>
                  )
                })}
              </div>
              {!loading && events.length === 0 && (
                <div
                  className="mt-8 text-center text-sm text-muted-foreground space-y-3"
                  data-testid="calendar-empty-month"
                >
                  <p>{t('calendar.empty_month')}</p>
                  <div className="flex justify-center gap-2">
                    <Button asChild size="sm">
                      <Link to="/audits">{t('calendar.schedule_audit')}</Link>
                    </Button>
                    <Button asChild size="sm" variant="outline">
                      <Link to="/actions">{t('calendar.create_action')}</Link>
                    </Button>
                  </div>
                </div>
              )}
            </>
          )}
        </Card>

        <div className="space-y-4">
          <Card className="p-4">
            <h3 className="font-semibold text-foreground mb-3">{t('calendar.event_types')}</h3>
            <ul className="space-y-2 text-sm">
              {ALL_TYPES.map((type) => (
                <li key={type} className="flex items-center gap-2 text-muted-foreground">
                  <span className={cn('h-2.5 w-2.5 rounded-full', TYPE_CHIP[type].dot)} />
                  {typeLabel(type)}
                </li>
              ))}
            </ul>
          </Card>

          <Card className="p-4" data-testid="calendar-upcoming">
            <div className="flex items-center justify-between mb-3">
              <h3 className="font-semibold text-foreground">
                {selectedDay
                  ? t('calendar.day_label', { date: toISODate(selectedDay) })
                  : t('calendar.upcoming')}
              </h3>
              {selectedDay && (
                <button
                  type="button"
                  className="text-muted-foreground hover:text-foreground"
                  onClick={() => setQuery({ day: null })}
                  aria-label={t('calendar.clear_day')}
                >
                  <X className="w-4 h-4" />
                </button>
              )}
            </div>
            <div className="space-y-3">
              {(selectedDay ? dayEvents : upcoming).length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  {selectedDay ? t('calendar.empty_day') : t('calendar.empty_upcoming')}
                </p>
              ) : (
                (selectedDay ? dayEvents : upcoming).map((event) => (
                  <div
                    key={event.id}
                    className="rounded-lg border border-border p-3 space-y-1"
                    title={[
                      event.title,
                      `${typeLabel(event.type)} · ${statusLabel(event.status)}`,
                      sourceModuleLabel(event.source_module),
                      event.owner ? `Owner: ${event.owner}` : '',
                      event.description || '',
                    ]
                      .filter(Boolean)
                      .join('\n')}
                  >
                    <div className="flex items-center gap-2">
                      <span className={cn('h-2 w-2 rounded-full', TYPE_CHIP[event.type]?.dot)} />
                      <span className="text-xs uppercase tracking-wide text-muted-foreground">
                        {typeLabel(event.type)}
                      </span>
                      <span className="text-xs text-muted-foreground">
                        · {sourceModuleLabel(event.source_module)}
                      </span>
                      {event.status === 'overdue' && (
                        <AlertTriangle className="w-3.5 h-3.5 text-destructive" />
                      )}
                    </div>
                    <p className="text-sm font-medium text-foreground leading-snug">{event.title}</p>
                    <p className="text-xs text-muted-foreground">{event.date}</p>
                    {event.href && (
                      <Link
                        to={event.href}
                        className="inline-flex items-center gap-1 text-xs text-primary hover:underline"
                      >
                        {t('calendar.open_source')} <ExternalLink className="w-3 h-3" />
                      </Link>
                    )}
                  </div>
                ))
              )}
            </div>
          </Card>
        </div>
      </div>
    </div>
  )
}
