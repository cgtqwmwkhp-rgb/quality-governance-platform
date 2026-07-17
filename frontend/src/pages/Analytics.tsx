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
  type ActionsSummary,
  type ExecutiveDashboardData,
} from '../api/client'
import type { AuditRun } from '../api/auditsClient'
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

interface ModuleRow {
  id: SectionId
  module: string
  total: number
  open: number
  closed: number
  avgResolutionDays: number | null
  trend: number | null
  href: string
  hrefOpen: string
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
  const [auditsTotal, setAuditsTotal] = useState(0)
  const [auditsOpen, setAuditsOpen] = useState(0)
  const [auditsClosed, setAuditsClosed] = useState(0)
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
      const [dashRes, actionsRes, viewCountsRes, riskRes, riskClosedRes, auditsRes, scoreRes] =
        await Promise.allSettled([
          executiveDashboardApi.getDashboard(days),
          actionsApi.summary(),
          actionsApi.viewCounts(),
          riskRegisterApi.getSummary(),
          riskRegisterApi.getSummary({ status: 'closed' }),
          auditsApi.listRuns(1, 100),
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
        setAuditsTotal(total)
        const runs: AuditRun[] = auditsRes.value.data.items ?? []
        const openOnPage = runs.filter(
          (r: AuditRun) => r.status !== 'completed' && r.status !== 'cancelled',
        ).length
        const closedOnPage = runs.filter((r: AuditRun) => r.status === 'completed').length
        if (total <= runs.length) {
          setAuditsOpen(openOnPage)
          setAuditsClosed(closedOnPage)
        } else {
          // Scale page mix to total when more runs exist than the page window.
          const ratioOpen = runs.length ? openOnPage / runs.length : 0
          const ratioClosed = runs.length ? closedOnPage / runs.length : 0
          setAuditsOpen(Math.round(total * ratioOpen))
          setAuditsClosed(Math.round(total * ratioClosed))
          notes.push('Audit open/closed mix estimated from first 100 runs')
        }
      } else {
        setAuditsTotal(0)
        setAuditsOpen(0)
        setAuditsClosed(0)
        notes.push('Audits list unavailable')
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
    const incidentsTotal = dash?.incidents.total_in_period ?? 0
    const incidentsOpen = dash?.incidents.open ?? 0
    const complaintsTotal = dash?.complaints.total_in_period ?? 0
    const complaintsOpen = dash?.complaints.open ?? 0
    const complaintsClosed = dash?.complaints.closed_in_period ?? 0
    const rtasTotal = dash?.rtas.total_in_period ?? 0
    const actionsTotal = actionsSummary?.total ?? 0
    const actionsOpen = openFromActions(actionsSummary)
    const actionsClosed = completedFromActions(actionsSummary)
    const riskOpen = Math.max(0, riskTotal)
    const nearMissTrend = dash?.near_misses.trend_percent ?? null

    return [
      {
        id: 'incidents',
        module: 'Incidents',
        total: incidentsTotal,
        open: incidentsOpen,
        closed: Math.max(0, incidentsTotal - Math.min(incidentsOpen, incidentsTotal)),
        avgResolutionDays: null,
        trend: nearMissTrend,
        href: '/incidents',
        hrefOpen: '/incidents?status=open',
      },
      {
        id: 'rtas',
        module: 'RTAs',
        total: rtasTotal,
        open: 0,
        closed: 0,
        avgResolutionDays: null,
        trend: null,
        href: '/rtas',
        hrefOpen: '/rtas',
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
      },
      {
        id: 'risks',
        module: 'Risks',
        total: riskOpen + riskClosed,
        open: riskOpen,
        closed: riskClosed,
        avgResolutionDays: null,
        trend: null,
        href: '/risk-register',
        hrefOpen: '/risk-register?status=active',
      },
      {
        id: 'audits',
        module: 'Audits',
        total: auditsTotal,
        open: auditsOpen,
        closed: auditsClosed,
        avgResolutionDays: null,
        trend: null,
        href: '/audits',
        hrefOpen: '/audits?view=board',
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
      },
    ]
  }, [dash, actionsSummary, riskTotal, riskClosed, auditsTotal, auditsOpen, auditsClosed])

  const filteredRows = useMemo(() => {
    let rows = moduleRows
    if (section !== 'home') {
      rows = rows.filter((r) => r.id === section)
    }
    if (heroFilter === 'open') {
      rows = rows.map((r) => ({ ...r })).filter((r) => r.open > 0 || section !== 'home')
    }
    if (heroFilter === 'high_priority') {
      // Keep all modules but section detail highlights priority metrics
      rows = rows
    }
    return rows
  }, [moduleRows, section, heroFilter])

  const totals = useMemo(() => {
    const total = moduleRows.reduce((a, b) => a + b.total, 0)
    const open = moduleRows.reduce((a, b) => a + b.open, 0)
    const closed = moduleRows.reduce((a, b) => a + b.closed, 0)
    const resolutionRate = total > 0 ? Math.round((closed / total) * 1000) / 10 : 0
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
    if (totals.open > 0) {
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
    if (lines.length === 0) {
      lines.push('No material hotspots in the loaded live metrics for this period.')
    }
    return lines
  }, [dash, actionsSummary, totals.open, timeRange, actionsOverdue, complianceScore])

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
            value: String(totals.total),
            icon: <FileText className="w-6 h-6" />,
            variant: 'info' as const,
          },
          {
            id: 'open' as HeroFilter,
            title: 'Open items',
            value: String(totals.open),
            icon: <Clock className="w-6 h-6" />,
            variant: 'warning' as const,
          },
          {
            id: 'resolution' as HeroFilter,
            title: 'Resolution rate',
            value: `${totals.resolutionRate}%`,
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
              const percentage = totals.total > 0 ? (stat.total / totals.total) * 100 : 0
              return (
                <button
                  key={stat.module}
                  type="button"
                  className="w-full space-y-2 text-left"
                  onClick={() => setQuery({ section: stat.id, hero: 'all' })}
                >
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-foreground">{stat.module}</span>
                    <span className="text-foreground font-medium">{stat.total}</span>
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
                  <td className="p-4 text-center text-foreground">{stat.total}</td>
                  <td className="p-4 text-center">
                    <span className="px-2 py-1 bg-warning/20 text-warning rounded-full text-sm">
                      {stat.open}
                    </span>
                  </td>
                  <td className="p-4 text-center">
                    <span className="px-2 py-1 bg-success/20 text-success rounded-full text-sm">
                      {stat.closed}
                    </span>
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
