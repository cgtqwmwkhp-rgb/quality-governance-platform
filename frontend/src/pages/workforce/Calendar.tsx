import { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { trackError } from '../../utils/errorTracker'
import { ChevronLeft, ChevronRight, AlertTriangle, GraduationCap } from 'lucide-react'
import { CardSkeleton } from '../../components/ui/SkeletonLoader'
import { useNavigate } from 'react-router-dom'
import { workforceApi, getApiErrorMessage, type AssessmentRun, type InductionRun } from '../../api/client'
import { cn } from '../../helpers/utils'

const DAY_KEYS = ['sun', 'mon', 'tue', 'wed', 'thu', 'fri', 'sat'] as const

interface CalendarEvent {
  date: number
  type: 'assessment' | 'induction'
  title: string
  overdue: boolean
  id: string
}

export default function Calendar() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [year, setYear] = useState(() => new Date().getFullYear())
  const [month, setMonth] = useState(() => new Date().getMonth())
  const [events, setEvents] = useState<CalendarEvent[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [engineerMap, setEngineerMap] = useState<Record<number, string>>({})

  useEffect(() => {
    workforceApi.listEngineers({ page: '1', page_size: '500' })
      .then((res) => {
        const map: Record<number, string> = {}
        for (const e of res.data?.items || []) {
          map[e.id] = e.employee_number || e.job_title || `#${e.id}`
        }
        setEngineerMap(map)
      })
      .catch(() => {})
  }, [])

  useEffect(() => {
    const load = async () => {
      setLoading(true)
      try {
        const [assessRes, inductRes] = await Promise.all([
          workforceApi.listAssessments({ page: '1', page_size: '500' }),
          workforceApi.listInductions({ page: '1', page_size: '500' }),
        ])
        const assessments = assessRes.data?.items || []
        const inductions = inductRes.data?.items || []

        const monthStart = new Date(year, month, 1)
        const monthEnd = new Date(year, month + 1, 0)
        const today = new Date()
        today.setHours(0, 0, 0, 0)

        const mapToEvents = (
          items: (AssessmentRun | InductionRun)[],
          type: 'assessment' | 'induction'
        ): CalendarEvent[] => {
          return items
            .filter((i) => {
              const d = i.scheduled_date ? new Date(i.scheduled_date) : null
              if (!d) return false
              return d >= monthStart && d <= monthEnd
            })
            .map((i) => {
              const d = i.scheduled_date ? new Date(i.scheduled_date) : new Date()
              const dayOfMonth = d.getDate()
              const overdue = d < today && i.status !== 'completed'
              const engName = engineerMap[i.engineer_id] ?? `#${i.engineer_id}`
              const title = `${i.reference_number} - ${engName}`
              return {
                date: dayOfMonth,
                type,
                title,
                overdue,
                id: i.id,
              }
            })
        }

        setEvents([
          ...mapToEvents(assessments, 'assessment'),
          ...mapToEvents(inductions, 'induction'),
        ])
      } catch (err) {
        trackError(err, { component: 'Calendar', action: 'load' })
        setError(getApiErrorMessage(err))
        setEvents([])
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [year, month, engineerMap])

  const firstDay = new Date(year, month, 1).getDay()
  const daysInMonth = new Date(year, month + 1, 0).getDate()
  const days: (number | null)[] = Array(firstDay).fill(null)
  for (let d = 1; d <= daysInMonth; d++) days.push(d)

  const monthName = new Date(year, month).toLocaleString('default', { month: 'long' })

  const getEventsForDay = (day: number) =>
    events.filter((e) => e.date === day)

  return (
    <div className="space-y-6">
      {error && (
        <div className="bg-destructive/10 text-destructive p-4 rounded-lg">{error}</div>
      )}
      <div>
        <h1 className="text-2xl font-bold text-foreground">{t('workforce.calendar.title')}</h1>
        <p className="text-muted-foreground mt-1">
          {t('workforce.calendar.subtitle')}
        </p>
      </div>

      {loading && (
        <CardSkeleton count={3} />
      )}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <button
            onClick={() => {
              if (month === 0) {
                setMonth(11)
                setYear((y) => y - 1)
              } else setMonth((m) => m - 1)
            }}
            className="p-2 rounded-lg border border-border bg-card text-foreground hover:bg-muted transition-colors"
          >
            <ChevronLeft className="w-5 h-5" />
          </button>
          <h2 className="text-xl font-semibold text-foreground min-w-[180px] text-center">
            {monthName} {year}
          </h2>
          <button
            onClick={() => {
              if (month === 11) {
                setMonth(0)
                setYear((y) => y + 1)
              } else setMonth((m) => m + 1)
            }}
            className="p-2 rounded-lg border border-border bg-card text-foreground hover:bg-muted transition-colors"
          >
            <ChevronRight className="w-5 h-5" />
          </button>
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

      <div className="rounded-xl border border-border bg-card overflow-hidden">
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
                "min-h-[100px] p-2 border-b border-r border-border/50",
                (i + 1) % 7 === 0 && "border-r-0"
              )}
            >
              {day !== null ? (
                <>
                  <div className="text-sm font-medium text-foreground mb-2">{day}</div>
                  <div className="space-y-1">
                    {getEventsForDay(day).map((ev) => (
                      <button
                        key={ev.id}
                        onClick={() =>
                          ev.type === 'assessment'
                            ? navigate(`/workforce/assessments/${ev.id}/execute`)
                            : navigate(`/workforce/training/${ev.id}/execute`)
                        }
                        className={cn(
                          "w-full text-left text-xs px-2 py-1.5 rounded border truncate block",
                          ev.type === 'assessment'
                            ? "border-warning/50 bg-warning/10 text-warning-foreground hover:bg-warning/20"
                            : "border-primary/30 bg-primary/10 text-primary-foreground hover:bg-primary/20",
                          ev.overdue && "border-destructive/50 bg-destructive/10"
                        )}
                        title={ev.title}
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
    </div>
  )
}
