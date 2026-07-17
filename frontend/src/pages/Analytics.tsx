import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import {
  BarChart3,
  TrendingUp,
  AlertTriangle,
  CheckCircle2,
  Clock,
  FileText,
  Shield,
  Activity,
  PieChart,
  ArrowUpRight,
  ArrowDownRight,
  Minus,
  RefreshCw,
  ExternalLink,
  Home,
  Loader2,
} from 'lucide-react'
import {
  actionsApi,
  auditsApi,
  complianceAutomationApi,
  executiveDashboardApi,
  getApiErrorMessage,
  riskRegisterApi,
  rtasApi,
  type ActionsSummary,
  type ExecutiveDashboardData,
} from '../api/client'
import type { AuditRun } from '../api/auditsClient'
import type { RTA } from '../api/rtasClient'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { cn } from '../helpers/utils'
import { toast } from '../contexts/ToastContext'

type TimeRange = '7d' | '30d' | '90d' | '1y'
type SectionId =
  | 'home'
  | 'incidents'
  | 'rtas'
  | 'complaints'
  | 'risks'
  | 'audits'
  | 'actions'

type HeroFilter =
  | 'all'
  | 'open'
  | 'high_priority'
  | 'compliance'
  | 'resolution'
  | 'total'

const PERIOD_DAYS: Record<TimeRange, number> = {
  '7d': 7,
  '30d': 30,
  '90d': 90,
  '1y': 365,
}

const SECTIONS: { id: SectionId; label: string; href: string }[] = [
  { id: 'home', label: 'Home', href: '/analytics' },
  { id: 'incidents', label: 'Incidents', href: '/incidents' },
  { id: 'rtas', label: 'RTAs', href: '/rtas' },
  { id: 'complaints', label: 'Complaints', href: '/complaints' },
  { id: 'risks', label: 'Risks', href: '/risk-register' },
  { id: 'audits', label: 'Audits', href: '/audits' },
  { id: 'actions', label: 'Actions', href: '/actions' },
]

type MetricValue = number | null
type ModuleLoadState = 'live' | 'unavailable' | 'estimated' | 'partial'

interface ModuleRow {
  id: SectionId
  module: string
  total: MetricValue
  open: MetricValue
  closed: MetricValue
  avgResolutionDays: number | null
  trend: number | null
  href: string
  hrefOpen: string
  loadState?: ModuleLoadState
}

function formatMetric(value: MetricValue): string {
  return value == null ? '—' : String(value)
}

function formatResolutionDays(value: number | null): string {
  return value == null ? '—' : `${value.toFixed(1)}d`
}

function avgResolutionDaysFromCompleted<T extends { created_at: string; completed_at?: string | null }>(
  items: T[],
): number | null {
  const durations = items
    .map((item) => {
      if (!item.completed_at) return null
      const start = new Date(item.created_at).getTime()
      const end = new Date(item.completed_at).getTime()
      if (!Number.isFinite(start) || !Number.isFinite(end) || end < start) return null
      return (end - start) / (1000 * 60 * 60 * 24)
    })
    .filter((days): days is number => days != null)
  if (durations.length === 0) return null
  return Math.round((durations.reduce((sum, days) => sum + days, 0) / durations.length) * 10) / 10
}

function avgResolutionDaysFromRtas(items: RTA[]): number | null {
  const durations = items
    .filter((rta) => rta.status === 'closed')
    .map((rta) => {
      const endSource = rta.updated_at ?? rta.reported_date
      if (!endSource) return null
      const start = new Date(rta.created_at).getTime()
      const end = new Date(endSource).getTime()
      if (!Number.isFinite(start) || !Number.isFinite(end) || end < start) return null
      return (end - start) / (1000 * 60 * 60 * 24)
    })
    .filter((days): days is number => days != null)
  if (durations.length === 0) return null
  return Math.round((durations.reduce((sum, days) => sum + days, 0) / durations.length) * 10) / 10
}

function sumMetrics(rows: ModuleRow[], key: 'total' | 'open' | 'closed'): number | null {
  const values = rows.map((row) => row[key]).filter((value): value is number => value != null)
  if (values.length === 0) return null
  return values.reduce((sum, value) => sum + value, 0)
}

function periodLabel(range: TimeRange) {
  return ({ '7d': '7 days', '30d': '30 days', '90d': '90 days', '1y': '12 months' } as const)[range]
}

function TrendIndicator({
  change,
  invertGood,
}: {
  change: number | null
  invertGood?: boolean
}) {
  if (change == null || Number.isNaN(change) || change === 0) {
    return (
      <span className="flex items-center gap-1 text-muted-foreground text-sm">
        <Minus className="w-4 h-4" />
        No change
      </span>
    )
  }
  const up = change > 0
  const good = invertGood ? !up : up
  const Icon = up ? ArrowUpRight : ArrowDownRight
  return (
    <span
      className={cn('flex items-center gap-1 text-sm', good ? 'text-success' : 'text-destructive')}
    >
      <Icon className="w-4 h-4" />
      {Math.abs(change).toFixed(1)}%
    </span>
  )
}

function completedFromActions(summary: ActionsSummary | null): number {
  if (!summary?.by_display_status) return 0
  return Number(summary.by_display_status.completed ?? summary.by_display_status.closed ?? 0)
}

function openFromActions(summary: ActionsSummary | null): number {
  if (!summary) return 0
  const by = summary.by_display_status ?? {}
  const completed = completedFromActions(summary)
  return Math.max(0, (summary.total ?? 0) - completed) ||
    Number(by.open ?? 0) + Number(by.in_progress ?? 0) + Number(by.overdue ?? 0)
}

export default function Analytics() {
  const [searchParams, setSearchParams] = useSearchParams()
  const sectionParam = (searchParams.get('section') as SectionId | null) ?? 'home'
  const section: SectionId = SECTIONS.some((s) => s.id === sectionParam) ? sectionParam : 'home'
  const rangeParam = searchParams.get('range') as TimeRange | null
  const timeRange: TimeRange = rangeParam && PERIOD_DAYS[rangeParam] ? rangeParam : '30d'
  const heroParam = (searchParams.get('hero') as HeroFilter | null) ?? 'all'
  const heroFilter: HeroFilter = [
    'all',
    'open',
    'high_priority',
    'compliance',
    'resolution',
    'total',
  ].includes(heroParam)
    ? heroParam
    : 'all'

  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [dash, setDash] = useState<ExecutiveDashboardData | null>(null)
  const [actionsSummary, setActionsSummary] = useState<ActionsSummary | null>(null)
  const [actionsOverdue, setActionsOverdue] = useState(0)
  const [riskTotal, setRiskTotal] = useState(0)
  const [riskClosed, setRiskClosed] = useState(0)
  const [auditsTotal, setAuditsTotal] = useState<number | null>(null)
  const [auditsOpen, setAuditsOpen] = useState<number | null>(null)
  const [auditsClosed, setAuditsClosed] = useState<number | null>(null)
  const [auditsAvgResolutionDays, setAuditsAvgResolutionDays] = useState<number | null>(null)
  const [auditsLoadState, setAuditsLoadState] = useState<ModuleLoadState>('unavailable')
  const [rtasOpen, setRtasOpen] = useState<number | null>(null)
  const [rtasClosed, setRtasClosed] = useState<number | null>(null)
  const [rtasAvgResolutionDays, setRtasAvgResolutionDays] = useState<number | null>(null)
  const [rtasLoadState, setRtasLoadState] = useState<ModuleLoadState>('unavailable')
  const [complianceScore, setComplianceScore] = useState<number | null>(null)
  const [partialNotes, setPartialNotes] = useState<string[]>([])

  const setQuery = useCallback(
    (patch: Record<string, string | null>) => {
      const next = new URLSearchParams(searchParams)
      Object.entries(patch).forEach(([key, value]) => {
        if (value == null || value === '' || (key === 'section' && value === 'home') || (key === 'hero' && value === 'all')) {
          if (key === 'section' && value === 'home') next.delete(key)
          else if (key === 'hero' && value === 'all') next.delete(key)
          else if (value == null || value === '') next.delete(key)
          else next.set(key, value)
        } else {
          next.set(key, value)
        }
      })
      setSearchParams(next, { replace: true })
    },
    [searchParams, setSearchParams],
  )

  const load = useCallback(async () => {
    const days = PERIOD_DAYS[timeRange]
    const notes: string[] = []
    try {
      setError(null)
      const [dashRes, actionsRes, viewCountsRes, riskRes, riskClosedRes, auditsRes, rtasRes, scoreRes] =
        await Promise.allSettled([
          executiveDashboardApi.getDashboard(days),
          actionsApi.summary(),
          actionsApi.viewCounts(),
          riskRegisterApi.getSummary(),
          riskRegisterApi.getSummary({ status: 'closed' }),
          auditsApi.listRuns(1, 100),
          rtasApi.list(1, 100),
          complianceAutomationApi.getComplianceScore({ scope_type: 'organization' }),
        ])

      if (dashRes.status === 'fulfilled') {
        setDash(dashRes.value.data)
      } else {
        setDash(null)
        notes.push('Executive dashboard unavailable')
      }

      if (actionsRes.status === 'fulfilled') {
        setActionsSummary(actionsRes.value.data)
      } else {
        setActionsSummary(null)
        notes.push('Actions summary unavailable')
      }

      if (viewCountsRes.status === 'fulfilled') {
        setActionsOverdue(viewCountsRes.value.data.overdue ?? 0)
      } else {
        setActionsOverdue(0)
      }

      if (riskRes.status === 'fulfilled') {
        setRiskTotal(riskRes.value.data.total_risks ?? 0)
      } else {
        setRiskTotal(0)
        notes.push('Risk register summary unavailable')
      }

      if (riskClosedRes.status === 'fulfilled') {
        setRiskClosed(riskClosedRes.value.data.total_risks ?? 0)
      } else {
        setRiskClosed(0)
      }

      if (auditsRes.status === 'fulfilled') {
        const total = auditsRes.value.data.total ?? 0
        const runs: AuditRun[] = auditsRes.value.data.items ?? []
        const openOnPage = runs.filter(
          (r: AuditRun) => r.status !== 'completed' && r.status !== 'cancelled',
        ).length
        const closedOnPage = runs.filter((r: AuditRun) => r.status === 'completed').length
        setAuditsTotal(total)
        setAuditsAvgResolutionDays(avgResolutionDaysFromCompleted(runs))
        if (total <= runs.length) {
          setAuditsOpen(openOnPage)
          setAuditsClosed(closedOnPage)
          setAuditsLoadState('live')
        } else {
          const ratioOpen = runs.length ? openOnPage / runs.length : 0
          const ratioClosed = runs.length ? closedOnPage / runs.length : 0
          setAuditsOpen(Math.round(total * ratioOpen))
          setAuditsClosed(Math.round(total * ratioClosed))
          setAuditsLoadState('estimated')
          notes.push('Audit open/closed mix estimated from first 100 runs')
        }
      } else {
        setAuditsTotal(null)
        setAuditsOpen(null)
        setAuditsClosed(null)
        setAuditsAvgResolutionDays(null)
        setAuditsLoadState('unavailable')
        notes.push('Audits list unavailable')
      }

      if (rtasRes.status === 'fulfilled') {
        const rtas: RTA[] = rtasRes.value.data.items ?? []
        const total = rtasRes.value.data.total ?? rtas.length
        const openOnPage = rtas.filter((rta) => rta.status !== 'closed').length
        const closedOnPage = rtas.filter((rta) => rta.status === 'closed').length
        setRtasAvgResolutionDays(avgResolutionDaysFromRtas(rtas))
        if (total <= rtas.length) {
          setRtasOpen(openOnPage)
          setRtasClosed(closedOnPage)
          setRtasLoadState('live')
        } else {
          const ratioOpen = rtas.length ? openOnPage / rtas.length : 0
          const ratioClosed = rtas.length ? closedOnPage / rtas.length : 0
          setRtasOpen(Math.round(total * ratioOpen))
          setRtasClosed(Math.round(total * ratioClosed))
          setRtasLoadState('estimated')
          notes.push('RTA open/closed mix estimated from first 100 records')
        }
      } else {
        setRtasOpen(null)
        setRtasClosed(null)
        setRtasAvgResolutionDays(null)
        setRtasLoadState('unavailable')
        notes.push('RTA list unavailable')
      }

      if (scoreRes.status === 'fulfilled') {
        const score = Number((scoreRes.value.data as { overall_score?: number }).overall_score)
        setComplianceScore(Number.isFinite(score) ? score : null)
      } else {
        setComplianceScore(null)
        notes.push('Compliance score unavailable')
      }

      setPartialNotes(notes)
      if (dashRes.status === 'rejected' && actionsRes.status === 'rejected') {
        setError('Unable to load analytics. Retry or check API health.')
      }
    } catch (err) {
      setError(getApiErrorMessage(err))
      toast.error(getApiErrorMessage(err))
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [timeRange])

  useEffect(() => {
    setLoading(true)
    void load()
  }, [load])

  const moduleRows: ModuleRow[] = useMemo(() => {
    const incidentsTotal = dash?.incidents.total_in_period ?? null
    const incidentsOpen = dash?.incidents.open ?? null
    const complaintsTotal = dash?.complaints.total_in_period ?? null
    const complaintsOpen = dash?.complaints.open ?? null
    const complaintsClosed = dash?.complaints.closed_in_period ?? null
    const rtasTotal = dash?.rtas.total_in_period ?? null
    const actionsTotal = actionsSummary?.total ?? null
    const actionsOpen = actionsSummary ? openFromActions(actionsSummary) : null
    const actionsClosed = actionsSummary ? completedFromActions(actionsSummary) : null
    const nearMissTrend = dash?.near_misses.trend_percent ?? null
    const incidentsClosed =
      incidentsTotal != null && incidentsOpen != null
        ? Math.max(0, incidentsTotal - Math.min(incidentsOpen, incidentsTotal))
        : null

    return [
      {
        id: 'incidents',
        module: 'Incidents',
        total: incidentsTotal,
        open: incidentsOpen,
        closed: incidentsClosed,
        avgResolutionDays: null,
        trend: nearMissTrend,
        href: '/incidents',
        hrefOpen: '/incidents?status=open',
        loadState: dash ? 'live' : 'unavailable',
      },
      {
        id: 'rtas',
        module: 'RTAs',
        total: rtasTotal,
        open: rtasOpen,
        closed: rtasClosed,
        avgResolutionDays: rtasAvgResolutionDays,
        trend: null,
        href: '/rtas',
        hrefOpen: '/rtas',
        loadState: rtasLoadState,
      },
      {
        id: 'complaints',
        module: 'Complaints',
        total: complaintsTotal,
        open: complaintsOpen,
        closed: complaintsClosed,
        avgResolutionDays: null,
        trend: dash?.complaints.resolution_rate != null ? null : null,
        href: '/complaints',
        hrefOpen: '/complaints?status=open',
        loadState: dash ? 'live' : 'unavailable',
      },
      {
        id: 'risks',
        module: 'Risks',
        total: riskTotal + riskClosed,
        open: riskTotal,
        closed: riskClosed,
        avgResolutionDays: null,
        trend: null,
        href: '/risk-register',
        hrefOpen: '/risk-register?status=active',
        loadState: 'live',
      },
      {
        id: 'audits',
        module: 'Audits',
        total: auditsTotal,
        open: auditsOpen,
        closed: auditsClosed,
        avgResolutionDays: auditsAvgResolutionDays,
        trend: null,
        href: '/audits',
        hrefOpen: '/audits?view=board',
        loadState: auditsLoadState,
      },
      {
        id: 'actions',
        module: 'Actions',
        total: actionsTotal,
        open: actionsOpen,
        closed: actionsClosed,
        avgResolutionDays: null,
        trend: null,
        href: '/actions',
        hrefOpen: '/actions?view=overdue',
        loadState: actionsSummary ? 'live' : 'unavailable',
      },
    ]
  }, [
    dash,
    actionsSummary,
    riskTotal,
    riskClosed,
    auditsTotal,
    auditsOpen,
    auditsClosed,
    auditsAvgResolutionDays,
    auditsLoadState,
    rtasOpen,
    rtasClosed,
    rtasAvgResolutionDays,
    rtasLoadState,
  ])

  const filteredRows = useMemo(() => {
    let rows = moduleRows
    if (section !== 'home') {
      rows = rows.filter((r) => r.id === section)
    }
    if (heroFilter === 'open') {
      rows = rows.map((r) => ({ ...r })).filter((r) => (r.open ?? 0) > 0 || section !== 'home')
    }
    if (heroFilter === 'high_priority') {
      // Keep all modules but section detail highlights priority metrics
      rows = rows
    }
    return rows
  }, [moduleRows, section, heroFilter])

  const totals = useMemo(() => {
    const total = sumMetrics(moduleRows, 'total')
    const open = sumMetrics(moduleRows, 'open')
    const closed = sumMetrics(moduleRows, 'closed')
    const resolutionRate =
      total != null && closed != null && total > 0
        ? Math.round((closed / total) * 1000) / 10
        : null
    const highPriority =
      (dash?.incidents.critical_high ?? 0) +
      (dash?.risks.high_critical ?? 0) +
      actionsOverdue
    return { total, open, closed, resolutionRate, highPriority }
  }, [moduleRows, dash, actionsOverdue])

  const weeklyTrends = dash?.trends?.incidents_weekly ?? []
  const maxTrend = Math.max(1, ...weeklyTrends.map((w) => w.count))

  const insights = useMemo(() => {
    const lines: string[] = []
    if (!dash && !actionsSummary) return lines
    if (totals.open != null && totals.open > 0) {
      lines.push(`${totals.open} open items across modules need attention in this ${periodLabel(timeRange)} view.`)
    }
    if ((dash?.incidents.critical_high ?? 0) > 0) {
      lines.push(
        `${dash!.incidents.critical_high} critical/high incidents in period — review Incidents and linked investigations.`,
      )
    }
    if (actionsOverdue > 0) {
      lines.push(`${actionsOverdue} overdue actions — open Actions with the Overdue filter.`)
    }
    if (complianceScore != null) {
      lines.push(
        `Evidence coverage score is ${complianceScore}% — drill into ISO Compliance for clause gaps.`,
      )
    }
    if ((dash?.complaints.resolution_rate ?? 0) > 0) {
      lines.push(`Complaint resolution rate this period: ${dash!.complaints.resolution_rate}%.`)
    }
    if (auditsLoadState === 'unavailable') {
      lines.push('Audit summary unavailable — open/closed counts are not shown as zero.')
    } else if (auditsLoadState === 'estimated') {
      lines.push('Audit open/closed mix is estimated from the first page of runs.')
    }
    if (rtasLoadState === 'unavailable') {
      lines.push('RTA open/closed unavailable — not shown as zero in the module table.')
    } else if (rtasLoadState === 'estimated') {
      lines.push('RTA open/closed mix is estimated from the first page of records.')
    }
    if (lines.length === 0) {
      lines.push('No material hotspots in the loaded live metrics for this period.')
    }
    return lines
  }, [
    dash,
    actionsSummary,
    totals.open,
    timeRange,
    actionsOverdue,
    complianceScore,
    auditsLoadState,
    rtasLoadState,
  ])

  const sectionMeta = SECTIONS.find((s) => s.id === section)!

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 text-primary animate-spin" />
      </div>
    )
  }

  return (
    <div className="space-y-6 animate-fade-in" data-testid="analytics-page">
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-foreground flex items-center gap-3">
            <div className="p-2 bg-primary/10 rounded-xl">
              <BarChart3 className="w-8 h-8 text-primary" />
            </div>
            Analytics Dashboard
          </h1>
          <p className="text-muted-foreground mt-1">
            Live cross-module insights — choose a section, filter heroes, drill to source data.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <div className="flex bg-surface rounded-lg p-1 border border-border" data-testid="analytics-range">
            {(['7d', '30d', '90d', '1y'] as const).map((range) => (
              <button
                key={range}
                type="button"
                onClick={() => setQuery({ range })}
                className={cn(
                  'px-3 py-1.5 text-sm font-medium rounded-md transition-all',
                  timeRange === range
                    ? 'bg-primary text-primary-foreground'
                    : 'text-muted-foreground hover:text-foreground',
                )}
              >
                {range}
              </button>
            ))}
          </div>

          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              setRefreshing(true)
              void load()
            }}
            disabled={refreshing}
          >
            <RefreshCw className={cn('w-4 h-4', refreshing && 'animate-spin')} />
          </Button>

          {section !== 'home' && (
            <Button variant="outline" size="sm" asChild>
              <Link to={sectionMeta.href}>
                <ExternalLink className="w-4 h-4 mr-2" />
                Open {sectionMeta.label}
              </Link>
            </Button>
          )}
        </div>
      </div>

      {/* Section chooser */}
      <div
        className="flex flex-wrap gap-2"
        role="tablist"
        aria-label="Analytics section"
        data-testid="analytics-sections"
      >
        {SECTIONS.map((s) => (
          <button
            key={s.id}
            type="button"
            role="tab"
            aria-selected={section === s.id}
            onClick={() => setQuery({ section: s.id === 'home' ? 'home' : s.id, hero: 'all' })}
            className={cn(
              'inline-flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm border transition-colors',
              section === s.id
                ? 'bg-primary text-primary-foreground border-primary'
                : 'bg-card border-border text-muted-foreground hover:text-foreground',
            )}
          >
            {s.id === 'home' ? <Home className="w-3.5 h-3.5" /> : null}
            {s.label}
          </button>
        ))}
      </div>

      {error && (
        <div role="alert" className="rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          {error}
        </div>
      )}

      {partialNotes.length > 0 && !error && (
        <div
          className="rounded-lg border border-warning/30 bg-warning/10 px-4 py-3 text-sm text-foreground"
          data-testid="analytics-partial"
        >
          Partial live data: {partialNotes.join(' · ')}
        </div>
      )}

      {/* Interactive hero KPIs */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4">
        {[
          {
            id: 'total' as HeroFilter,
            title: 'Total records',
            value: formatMetric(totals.total),
            icon: <FileText className="w-6 h-6" />,
            variant: 'info' as const,
          },
          {
            id: 'open' as HeroFilter,
            title: 'Open items',
            value: formatMetric(totals.open),
            icon: <Clock className="w-6 h-6" />,
            variant: 'warning' as const,
          },
          {
            id: 'resolution' as HeroFilter,
            title: 'Resolution rate',
            value: totals.resolutionRate != null ? `${totals.resolutionRate}%` : '—',
            icon: <CheckCircle2 className="w-6 h-6" />,
            variant: 'success' as const,
          },
          {
            id: 'all' as HeroFilter,
            title: 'Health score',
            value: dash?.health_score?.score != null ? String(dash.health_score.score) : '—',
            icon: <Activity className="w-6 h-6" />,
            variant: 'primary' as const,
          },
          {
            id: 'compliance' as HeroFilter,
            title: 'Compliance score',
            value: complianceScore != null ? `${complianceScore}%` : '—',
            icon: <Shield className="w-6 h-6" />,
            variant: 'info' as const,
          },
          {
            id: 'high_priority' as HeroFilter,
            title: 'High priority',
            value: String(totals.highPriority),
            icon: <AlertTriangle className="w-6 h-6" />,
            variant: 'destructive' as const,
          },
        ].map((kpi) => (
          <button
            key={kpi.id + kpi.title}
            type="button"
            data-testid={`analytics-hero-${kpi.id}`}
            onClick={() => {
              setQuery({ hero: heroFilter === kpi.id ? 'all' : kpi.id })
              if (kpi.id === 'compliance') {
                // keep section; user can open ISO from insights
              }
              if (kpi.id === 'high_priority' && section === 'home') {
                // no-op section
              }
            }}
            className={cn(
              'text-left rounded-xl border p-4 transition-colors bg-card',
              heroFilter === kpi.id ? 'border-primary ring-2 ring-primary/20' : 'border-border hover:border-primary/40',
            )}
          >
            <div className="flex items-start justify-between mb-3">
              <div
                className={cn(
                  'p-2 rounded-lg',
                  kpi.variant === 'primary' && 'bg-primary/10 text-primary',
                  kpi.variant === 'info' && 'bg-info/10 text-info',
                  kpi.variant === 'warning' && 'bg-warning/10 text-warning',
                  kpi.variant === 'success' && 'bg-success/10 text-success',
                  kpi.variant === 'destructive' && 'bg-destructive/10 text-destructive',
                )}
              >
                {kpi.icon}
              </div>
            </div>
            <p className="text-2xl font-bold text-foreground">{kpi.value}</p>
            <p className="text-sm text-muted-foreground">{kpi.title}</p>
          </button>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card className="lg:col-span-2 p-6">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-lg font-semibold text-foreground flex items-center gap-2">
              <TrendingUp className="w-5 h-5 text-primary" />
              Incident weekly trend
            </h2>
            <span className="text-xs text-muted-foreground">{periodLabel(timeRange)} · live</span>
          </div>
          <div className="h-64 flex items-end justify-between gap-2" data-testid="analytics-trends">
            {weeklyTrends.length === 0 ? (
              <div className="flex-1 flex items-center justify-center text-muted-foreground text-sm">
                No incident trend points for this period
              </div>
            ) : (
              weeklyTrends.map((week) => (
                <div key={week.week_start} className="flex-1 flex flex-col items-center gap-1 min-w-0">
                  <div
                    className="w-full max-w-[28px] bg-info rounded-t transition-all"
                    style={{ height: `${(week.count / maxTrend) * 200}px`, minHeight: week.count ? 4 : 0 }}
                    title={`${week.week_start}: ${week.count}`}
                  />
                  <span className="text-[10px] text-muted-foreground truncate w-full text-center">
                    {week.week_start.slice(5)}
                  </span>
                </div>
              ))
            )}
          </div>
        </Card>

        <Card className="p-6">
          <h2 className="text-lg font-semibold text-foreground flex items-center gap-2 mb-6">
            <PieChart className="w-5 h-5 text-primary" />
            Module distribution
          </h2>
          <div className="space-y-4">
            {moduleRows.map((stat) => {
              const percentage =
                totals.total != null && stat.total != null && totals.total > 0
                  ? (stat.total / totals.total) * 100
                  : 0
              return (
                <button
                  key={stat.module}
                  type="button"
                  className="w-full space-y-2 text-left"
                  onClick={() => setQuery({ section: stat.id, hero: 'all' })}
                >
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-foreground">{stat.module}</span>
                    <span className="text-foreground font-medium">{formatMetric(stat.total)}</span>
                  </div>
                  <div className="h-2 bg-surface rounded-full overflow-hidden">
                    <div
                      className="h-full rounded-full bg-primary transition-all"
                      style={{ width: `${percentage}%` }}
                    />
                  </div>
                </button>
              )
            })}
          </div>
        </Card>
      </div>

      <Card className="overflow-hidden">
        <div className="p-6 border-b border-border flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <h2 className="text-lg font-semibold text-foreground flex items-center gap-2">
            <Activity className="w-5 h-5 text-primary" />
            {section === 'home' ? 'Module performance' : `${sectionMeta.label} detail`}
          </h2>
          <p className="text-xs text-muted-foreground">
            Click a row to focus the section · use Open source for the live register
          </p>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full" data-testid="analytics-module-table">
            <thead className="bg-surface">
              <tr>
                <th className="text-left p-4 text-sm font-medium text-muted-foreground">Module</th>
                <th className="text-center p-4 text-sm font-medium text-muted-foreground">Total</th>
                <th className="text-center p-4 text-sm font-medium text-muted-foreground">Open</th>
                <th className="text-center p-4 text-sm font-medium text-muted-foreground">Closed</th>
                <th className="text-center p-4 text-sm font-medium text-muted-foreground">Avg resolution</th>
                <th className="text-center p-4 text-sm font-medium text-muted-foreground">Trend</th>
                <th className="text-right p-4 text-sm font-medium text-muted-foreground">Source</th>
              </tr>
            </thead>
            <tbody>
              {filteredRows.map((stat) => (
                <tr
                  key={stat.module}
                  className={cn(
                    'border-b border-border hover:bg-surface transition-colors cursor-pointer',
                    section === stat.id && 'bg-primary/5',
                  )}
                  onClick={() => setQuery({ section: stat.id })}
                >
                  <td className="p-4 font-medium text-foreground">{stat.module}</td>
                  <td className="p-4 text-center text-foreground">{formatMetric(stat.total)}</td>
                  <td className="p-4 text-center">
                    <span
                      className={cn(
                        'px-2 py-1 rounded-full text-sm',
                        stat.open == null
                          ? 'bg-muted text-muted-foreground'
                          : 'bg-warning/20 text-warning',
                      )}
                    >
                      {formatMetric(stat.open)}
                    </span>
                  </td>
                  <td className="p-4 text-center">
                    <span
                      className={cn(
                        'px-2 py-1 rounded-full text-sm',
                        stat.closed == null
                          ? 'bg-muted text-muted-foreground'
                          : 'bg-success/20 text-success',
                      )}
                    >
                      {formatMetric(stat.closed)}
                    </span>
                  </td>
                  <td className="p-4 text-center text-muted-foreground">
                    {formatResolutionDays(stat.avgResolutionDays)}
                  </td>
                  <td className="p-4 text-center">
                    <TrendIndicator change={stat.trend} invertGood />
                  </td>
                  <td className="p-4 text-right">
                    <Link
                      to={heroFilter === 'open' || heroFilter === 'high_priority' ? stat.hrefOpen : stat.href}
                      className="inline-flex items-center gap-1 text-sm text-primary hover:underline"
                      onClick={(e) => e.stopPropagation()}
                    >
                      Open source <ExternalLink className="w-3.5 h-3.5" />
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      {section !== 'home' && (
        <Card className="p-6" data-testid="analytics-section-panel">
          <h3 className="text-lg font-semibold text-foreground mb-2">{sectionMeta.label} — live slice</h3>
          <p className="text-sm text-muted-foreground mb-4">
            Metrics below are from the same upstream APIs as the operational screens. Use Open source
            for the full register with filters applied where available.
          </p>
          <div className="flex flex-wrap gap-3">
            <Button asChild>
              <Link to={sectionMeta.href}>Go to {sectionMeta.label}</Link>
            </Button>
            {section === 'actions' && (
              <Button variant="outline" asChild>
                <Link to="/actions?view=overdue">Overdue actions ({actionsOverdue})</Link>
              </Button>
            )}
            {section === 'incidents' && (
              <Button variant="outline" asChild>
                <Link to="/incidents">
                  Critical/high in period: {dash?.incidents.critical_high ?? 0}
                </Link>
              </Button>
            )}
            {section === 'risks' && (
              <Button variant="outline" asChild>
                <Link to="/risk-register">High/critical risks: {dash?.risks.high_critical ?? 0}</Link>
              </Button>
            )}
            {section === 'audits' && (
              <Card className="w-full p-4 border-warning/30 bg-warning/5" data-testid="analytics-audit-summary">
                <h4 className="font-semibold text-foreground mb-2">Audit summary</h4>
                {auditsLoadState === 'unavailable' ? (
                  <p className="text-sm text-muted-foreground">
                    Audit metrics unavailable — counts are not shown as zero.
                  </p>
                ) : (
                  <>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
                      <div>
                        <p className="text-muted-foreground">Total</p>
                        <p className="text-lg font-semibold text-foreground">{formatMetric(auditsTotal)}</p>
                      </div>
                      <div>
                        <p className="text-muted-foreground">Open</p>
                        <p className="text-lg font-semibold text-foreground">{formatMetric(auditsOpen)}</p>
                      </div>
                      <div>
                        <p className="text-muted-foreground">Closed</p>
                        <p className="text-lg font-semibold text-foreground">{formatMetric(auditsClosed)}</p>
                      </div>
                      <div>
                        <p className="text-muted-foreground">Avg resolution</p>
                        <p className="text-lg font-semibold text-foreground">
                          {formatResolutionDays(auditsAvgResolutionDays)}
                        </p>
                      </div>
                    </div>
                    {auditsLoadState === 'estimated' && (
                      <p className="mt-3 text-xs text-muted-foreground">
                        Open/closed mix estimated from the first 100 runs — use Audits for authoritative counts.
                      </p>
                    )}
                    {auditsAvgResolutionDays == null && auditsLoadState !== 'unavailable' && (
                      <p className="mt-3 text-xs text-muted-foreground">
                        Avg resolution unavailable — no completed runs with completion timestamps in the loaded page.
                      </p>
                    )}
                  </>
                )}
              </Card>
            )}
            {section === 'rtas' && (
              <Card className="w-full p-4 border-warning/30 bg-warning/5" data-testid="analytics-rta-summary">
                <h4 className="font-semibold text-foreground mb-2">RTA summary</h4>
                {rtasLoadState === 'unavailable' ? (
                  <p className="text-sm text-muted-foreground">
                    RTA open/closed unavailable — not shown as zero.
                  </p>
                ) : (
                  <>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
                      <div>
                        <p className="text-muted-foreground">Total in period</p>
                        <p className="text-lg font-semibold text-foreground">
                          {formatMetric(moduleRows.find((row) => row.id === 'rtas')?.total ?? null)}
                        </p>
                      </div>
                      <div>
                        <p className="text-muted-foreground">Open</p>
                        <p className="text-lg font-semibold text-foreground">{formatMetric(rtasOpen)}</p>
                      </div>
                      <div>
                        <p className="text-muted-foreground">Closed</p>
                        <p className="text-lg font-semibold text-foreground">{formatMetric(rtasClosed)}</p>
                      </div>
                      <div>
                        <p className="text-muted-foreground">Avg resolution</p>
                        <p className="text-lg font-semibold text-foreground">
                          {formatResolutionDays(rtasAvgResolutionDays)}
                        </p>
                      </div>
                    </div>
                    {rtasLoadState === 'estimated' && (
                      <p className="mt-3 text-xs text-muted-foreground">
                        Open/closed mix estimated from the first 100 records — use RTAs for authoritative counts.
                      </p>
                    )}
                    {rtasAvgResolutionDays == null && (
                      <p className="mt-3 text-xs text-muted-foreground">
                        Avg resolution unavailable — no closed RTAs with usable timestamps in the loaded page.
                      </p>
                    )}
                  </>
                )}
              </Card>
            )}
            {heroFilter === 'compliance' && (
              <Button variant="outline" asChild>
                <Link to="/compliance">ISO Compliance coverage</Link>
              </Button>
            )}
          </div>
        </Card>
      )}

      <Card className="p-6 border-primary/20 bg-primary/5">
        <h3 className="text-lg font-semibold text-foreground mb-2">Live insights</h3>
        <ul className="space-y-2 text-muted-foreground text-sm">
          {insights.map((line) => (
            <li key={line}>
              • <span className="text-foreground">{line}</span>
            </li>
          ))}
        </ul>
        <div className="mt-4 flex flex-wrap gap-2">
          <Button variant="outline" size="sm" asChild>
            <Link to="/compliance">ISO Compliance</Link>
          </Button>
          <Button variant="outline" size="sm" asChild>
            <Link to="/ims">IMS Overview</Link>
          </Button>
          <Button variant="outline" size="sm" asChild>
            <Link to="/compliance-automation">Monitoring</Link>
          </Button>
        </div>
      </Card>
    </div>
  )
}
