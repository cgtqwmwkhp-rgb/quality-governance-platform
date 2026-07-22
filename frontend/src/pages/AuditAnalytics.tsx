import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  Download,
  Loader2,
  ListChecks,
  RefreshCw,
  ShieldAlert,
  TrendingUp,
} from 'lucide-react'
import { auditsApi, getApiErrorMessage } from '../api/client'
import type {
  AuditAnalyticsDimensionItem,
  AuditAnalyticsGroupBy,
  AuditAnalyticsSummary,
  CriticalQueueItem,
} from '../api/auditsClient'
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/Card'
import { Button } from '../components/ui/Button'

type TimeRange = '30d' | '90d' | '180d' | '365d'

const PERIOD_DAYS: Record<TimeRange, number> = { '30d': 30, '90d': 90, '180d': 180, '365d': 365 }

const GROUP_BY_OPTIONS: { value: AuditAnalyticsGroupBy; label: string }[] = [
  { value: 'asset_type', label: 'Asset type' },
  { value: 'assessment_mode', label: 'Assessment mode' },
  { value: 'template', label: 'Template' },
  { value: 'criticality', label: 'Criticality' },
  { value: 'customer', label: 'Customer' },
  { value: 'location', label: 'Location' },
  { value: 'engineer', label: 'Engineer' },
  { value: 'week', label: 'Week' },
]

function formatPercent(value: number | null | undefined): string {
  return value == null ? '—' : `${value.toFixed(1)}%`
}

/** Queue title uses the uncapped KPI total; list may still be capped (e.g. 200). */
export function formatCriticalQueueHeading(
  totalCount: number | null | undefined,
  shownCount: number,
): string {
  const total = totalCount ?? shownCount
  if (shownCount > 0 && total > shownCount) {
    return `Critical items queue (showing ${shownCount} of ${total})`
  }
  return `Critical items queue (${total})`
}

/** Heatmap-style cell shading: green for healthy, amber/red as fail rate climbs. */
function failRateClass(failRate: number): string {
  if (failRate >= 25) return 'bg-destructive/15 text-destructive'
  if (failRate >= 10) return 'bg-warning/15 text-warning'
  if (failRate > 0) return 'bg-success/10 text-success'
  return 'text-muted-foreground'
}

function essentialComplianceClass(pct: number | null | undefined): string {
  if (pct == null) return 'text-muted-foreground'
  if (pct < 80) return 'bg-destructive/15 text-destructive'
  if (pct < 95) return 'bg-warning/15 text-warning'
  return 'bg-success/10 text-success'
}

export default function AuditAnalytics() {
  const [range, setRange] = useState<TimeRange>('90d')
  const [groupBy, setGroupBy] = useState<AuditAnalyticsGroupBy>('asset_type')
  const [summary, setSummary] = useState<AuditAnalyticsSummary | null>(null)
  const [dimensions, setDimensions] = useState<AuditAnalyticsDimensionItem[]>([])
  const [criticalQueue, setCriticalQueue] = useState<CriticalQueueItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [exporting, setExporting] = useState(false)
  const days = useMemo(() => PERIOD_DAYS[range], [range])

  const loadAll = async () => {
    setLoading(true)
    setError(null)
    try {
      const [summaryRes, dimensionsRes, queueRes] = await Promise.all([
        auditsApi.getAnalyticsSummary(days),
        auditsApi.getAnalyticsDimensions(groupBy, days),
        auditsApi.getCriticalQueue(200),
      ])
      setSummary(summaryRes.data)
      setDimensions(dimensionsRes.data.items)
      setCriticalQueue(queueRes.data.items)
    } catch (err) {
      setError(getApiErrorMessage(err, 'Could not load audit analytics.'))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void loadAll()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [days, groupBy])

  const handleExport = async () => {
    setExporting(true)
    try {
      const res = await auditsApi.exportAnalyticsCsv(days)
      const url = URL.createObjectURL(res.data)
      const link = document.createElement('a')
      link.href = url
      link.download = `audit-analytics-${days}d.csv`
      document.body.appendChild(link)
      link.click()
      link.remove()
      URL.revokeObjectURL(url)
    } catch (err) {
      setError(getApiErrorMessage(err, 'Could not export audit analytics CSV.'))
    } finally {
      setExporting(false)
    }
  }

  const kpiCards = [
    {
      label: 'Total runs',
      value: summary ? String(summary.totals) : '—',
      icon: ListChecks,
      accent: 'text-primary',
    },
    {
      label: 'Completed',
      value: summary ? String(summary.completed) : '—',
      icon: CheckCircle2,
      accent: 'text-success',
    },
    {
      label: 'Pass rate',
      value: summary ? formatPercent(summary.pass_rate) : '—',
      icon: TrendingUp,
      accent: 'text-primary',
    },
    {
      label: 'Essential compliance',
      value: summary ? formatPercent(summary.essential_compliance_pct) : '—',
      icon: ShieldAlert,
      accent:
        summary && summary.essential_compliance_pct < 95 ? 'text-destructive' : 'text-success',
    },
    {
      label: 'Incomplete critical items',
      value: summary ? String(summary.incomplete_critical_count) : '—',
      icon: AlertTriangle,
      accent: summary && summary.incomplete_critical_count > 0 ? 'text-warning' : 'text-success',
    },
  ]

  return (
    <div className="min-h-screen bg-background">
      <div className="max-w-7xl mx-auto px-4 py-6 space-y-6">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div className="flex items-center gap-3">
            <Link
              to="/audits"
              className="p-2 rounded-lg hover:bg-secondary text-muted-foreground"
              aria-label="Back to audits"
            >
              <ArrowLeft className="w-5 h-5" />
            </Link>
            <div>
              <h1 className="text-xl font-bold text-foreground">Audit Analytics</h1>
              <p className="text-sm text-muted-foreground">
                Reporting pack — composition-aware pass rates, essential compliance, and the
                critical-items queue.
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <select
              value={range}
              onChange={(e) => setRange(e.target.value as TimeRange)}
              className="px-3 py-2 bg-secondary border border-border rounded-lg text-sm text-foreground"
              aria-label="Time range"
            >
              <option value="30d">Last 30 days</option>
              <option value="90d">Last 90 days</option>
              <option value="180d">Last 180 days</option>
              <option value="365d">Last 12 months</option>
            </select>
            <Button variant="outline" size="sm" onClick={() => void loadAll()} disabled={loading}>
              <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
              Refresh
            </Button>
            <Button size="sm" onClick={() => void handleExport()} disabled={exporting}>
              {exporting ? (
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              ) : (
                <Download className="w-4 h-4 mr-2" />
              )}
              Export CSV
            </Button>
          </div>
        </div>

        {error && (
          <div className="rounded-xl border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
            {error}
          </div>
        )}

        {/* Summary KPI cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
          {kpiCards.map(({ label, value, icon: Icon, accent }) => (
            <Card key={label}>
              <CardContent className="p-4 flex items-center justify-between">
                <div>
                  <p className="text-xs text-muted-foreground">{label}</p>
                  <p className={`text-2xl font-bold mt-1 ${accent}`}>
                    {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : value}
                  </p>
                </div>
                <Icon className={`w-6 h-6 ${accent} opacity-70`} />
              </CardContent>
            </Card>
          ))}
        </div>

        {/* Dimensions heatmap */}
        <Card>
          <CardHeader className="flex-row items-center justify-between space-y-0">
            <CardTitle>Breakdown by dimension</CardTitle>
            <select
              value={groupBy}
              onChange={(e) => setGroupBy(e.target.value as AuditAnalyticsGroupBy)}
              className="px-3 py-1.5 bg-secondary border border-border rounded-lg text-sm text-foreground"
              aria-label="Group by"
            >
              {GROUP_BY_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </CardHeader>
          <CardContent>
            {loading ? (
              <div className="flex items-center justify-center py-10">
                <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
              </div>
            ) : dimensions.length === 0 ? (
              <p className="text-sm text-muted-foreground py-6 text-center">
                No audit runs in this period yet.
              </p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm" data-testid="audit-analytics-dimensions-table">
                  <thead>
                    <tr className="text-left text-xs text-muted-foreground border-b border-border">
                      <th className="py-2 pr-3">
                        {GROUP_BY_OPTIONS.find((g) => g.value === groupBy)?.label}
                      </th>
                      <th className="py-2 pr-3">Runs</th>
                      <th className="py-2 pr-3">Completed</th>
                      <th className="py-2 pr-3">Avg score</th>
                      <th className="py-2 pr-3">Fail rate</th>
                      <th className="py-2 pr-3">Essential compliance</th>
                    </tr>
                  </thead>
                  <tbody>
                    {dimensions.map((item) => (
                      <tr key={item.key} className="border-b border-border/50">
                        <td className="py-2 pr-3 font-medium text-foreground">{item.label}</td>
                        <td className="py-2 pr-3">{item.run_count}</td>
                        <td className="py-2 pr-3">{item.completed_count}</td>
                        <td className="py-2 pr-3">{item.avg_score.toFixed(1)}%</td>
                        <td className="py-2 pr-3">
                          <span
                            className={`px-2 py-0.5 rounded-full text-xs font-medium ${failRateClass(item.fail_rate)}`}
                          >
                            {item.fail_rate.toFixed(1)}%
                          </span>
                        </td>
                        <td className="py-2 pr-3">
                          <span
                            className={`px-2 py-0.5 rounded-full text-xs font-medium ${essentialComplianceClass(item.essential_compliance_pct)}`}
                          >
                            {formatPercent(item.essential_compliance_pct)}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Critical queue */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <AlertTriangle className="w-5 h-5 text-warning" />
              {formatCriticalQueueHeading(summary?.incomplete_critical_count, criticalQueue.length)}
            </CardTitle>
          </CardHeader>
          <CardContent>
            {loading ? (
              <div className="flex items-center justify-center py-10">
                <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
              </div>
            ) : criticalQueue.length === 0 ? (
              <p className="text-sm text-muted-foreground py-6 text-center">
                No incomplete essential items — nice work.
              </p>
            ) : (
              <ul className="divide-y divide-border/50" data-testid="audit-analytics-critical-queue">
                {criticalQueue.map((item) => (
                  <li
                    key={`${item.run_id}-${item.question_id}`}
                    className="py-3 flex items-center justify-between gap-3"
                  >
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-foreground truncate">
                        {item.question_text}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {item.template_name || `Template #${item.template_id}`} ·{' '}
                        {item.run_reference_number || `Run #${item.run_id}`} ·{' '}
                        {item.reason === 'unanswered'
                          ? 'Unanswered essential question'
                          : `Open finding (${item.finding_status})`}
                      </p>
                    </div>
                    <Link
                      to={`/audits/${item.run_id}/execute`}
                      className="shrink-0 text-xs font-medium text-primary hover:underline"
                    >
                      Go to run →
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
