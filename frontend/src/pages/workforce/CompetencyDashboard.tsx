import { useState, useEffect, useMemo } from 'react'
import { Users, Award, Clock, AlertTriangle, TrendingUp, ClipboardCheck, BookOpen } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { workforceApi } from '../../api/client'
import { Card, CardContent, CardHeader } from '../../components/ui/Card'
import { cn } from '../../helpers/utils'

const KPI_CARDS = [
  { key: 'engineers', label: 'Total Engineers', icon: Users, color: 'text-primary' },
  { key: 'active', label: 'Active Competencies', icon: Award, color: 'text-success' },
  { key: 'expiring', label: 'Expiring Soon', icon: Clock, color: 'text-warning' },
  { key: 'overdue', label: 'Overdue', icon: AlertTriangle, color: 'text-destructive' },
]

const STATUS_COLORS: Record<string, string> = {
  active: 'bg-success',
  due: 'bg-warning',
  expired: 'bg-destructive',
  failed: 'bg-destructive/60',
  not_assessed: 'bg-muted-foreground/40',
}

const STATUS_LABELS: Record<string, string> = {
  active: 'Current',
  due: 'Expiring Soon',
  expired: 'Expired',
  failed: 'Failed',
  not_assessed: 'Not Assessed',
}

type TrendMonth = { month: string | null; total: number; passed: number; failed: number }

export default function CompetencyDashboard() {
  const navigate = useNavigate()
  const [loading, setLoading] = useState(true)
  const [kpis, setKpis] = useState({ engineers: 0, active: 0, expiring: 0, overdue: 0 })
  const [competencyBreakdown, setCompetencyBreakdown] = useState<Record<string, number>>({})
  const [assessments, setAssessments] = useState<{ id: string; reference_number: string; status: string; title?: string }[]>([])
  const [trends, setTrends] = useState<TrendMonth[]>([])

  useEffect(() => {
    const load = async () => {
      setLoading(true)
      try {
        const [summaryRes, assessRes, trendsRes] = await Promise.all([
          workforceApi.getWdpSummary(),
          workforceApi.listAssessments({ page: '1', page_size: '5' }),
          workforceApi.getWdpTrends(),
        ])
        const s = summaryRes.data
        setKpis({
          engineers: s?.engineers?.total ?? 0,
          active: s?.competencies?.active ?? 0,
          expiring: s?.competencies?.due ?? 0,
          overdue: s?.competencies?.expired ?? 0,
        })
        setCompetencyBreakdown(s?.competencies ?? {})
        setAssessments(assessRes.data?.items || [])
        setTrends(trendsRes.data?.assessments_by_month || [])
      } catch {
        setKpis({ engineers: 0, active: 0, expiring: 0, overdue: 0 })
        setCompetencyBreakdown({})
        setAssessments([])
        setTrends([])
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  const compTotal = useMemo(
    () => Object.values(competencyBreakdown).reduce((a, b) => a + b, 0),
    [competencyBreakdown]
  )

  const trendMax = useMemo(
    () => Math.max(1, ...trends.map((t) => t.total)),
    [trends]
  )

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-foreground">Competency Dashboard</h1>
        <p className="text-muted-foreground mt-1">
          Workforce development analytics and overview
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {KPI_CARDS.map((k) => (
          <Card key={k.key} hoverable>
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-muted-foreground">{k.label}</p>
                  <p className="text-2xl font-bold text-foreground mt-1">
                    {kpis[k.key as keyof typeof kpis] ?? 0}
                  </p>
                </div>
                <div className={cn("p-3 rounded-lg bg-muted", k.color)}>
                  <k.icon className="w-6 h-6" />
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Competency breakdown - real data-driven horizontal bar */}
        <Card>
          <CardHeader>
            <h2 className="text-lg font-semibold text-foreground">
              Competency Status Breakdown
            </h2>
            <p className="text-sm text-muted-foreground">
              {compTotal} total competency records
            </p>
          </CardHeader>
          <CardContent>
            {compTotal === 0 ? (
              <div className="flex flex-col items-center justify-center h-48 text-muted-foreground gap-2">
                <Award className="w-10 h-10" />
                <p className="text-sm">No competency data yet</p>
                <p className="text-xs">Complete assessments to populate this chart</p>
              </div>
            ) : (
              <div className="space-y-3">
                {Object.entries(competencyBreakdown)
                  .filter(([, count]) => count > 0)
                  .sort(([, a], [, b]) => b - a)
                  .map(([state, count]) => {
                    const pct = Math.round((count / compTotal) * 100)
                    return (
                      <div key={state} className="space-y-1">
                        <div className="flex items-center justify-between text-sm">
                          <span className="font-medium text-foreground">
                            {STATUS_LABELS[state] ?? state.replace(/_/g, ' ')}
                          </span>
                          <span className="text-muted-foreground">{count} ({pct}%)</span>
                        </div>
                        <div className="h-3 rounded-full bg-muted overflow-hidden">
                          <div
                            className={cn("h-full rounded-full transition-all", STATUS_COLORS[state] ?? 'bg-primary')}
                            style={{ width: `${pct}%` }}
                          />
                        </div>
                      </div>
                    )
                  })}
              </div>
            )}
            <div className="mt-4 flex flex-wrap gap-4 text-sm">
              {Object.entries(STATUS_LABELS).map(([key, label]) => (
                <span key={key} className="flex items-center gap-2">
                  <span className={cn("w-3 h-3 rounded-full", STATUS_COLORS[key])} />
                  {label}
                </span>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Assessment Trends - bar chart */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-lg font-semibold text-foreground">Assessment Trends</h2>
                <p className="text-sm text-muted-foreground">Monthly pass/fail over last 12 months</p>
              </div>
              <TrendingUp className="w-5 h-5 text-muted-foreground" />
            </div>
          </CardHeader>
          <CardContent>
            {trends.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-48 text-muted-foreground gap-2">
                <TrendingUp className="w-10 h-10" />
                <p className="text-sm">No trend data yet</p>
                <p className="text-xs">Assessment history will appear here</p>
              </div>
            ) : (
              <>
                <div className="flex items-end gap-1 h-40">
                  {trends.map((t, i) => {
                    const passH = (t.passed / trendMax) * 100
                    const failH = (t.failed / trendMax) * 100
                    const monthLabel = t.month
                      ? new Date(t.month).toLocaleDateString('en-GB', { month: 'short' })
                      : ''
                    return (
                      <div key={i} className="flex-1 flex flex-col items-center gap-0.5" title={`${monthLabel}: ${t.total} total, ${t.passed} passed, ${t.failed} failed`}>
                        <div className="w-full flex flex-col items-center justify-end" style={{ height: '120px' }}>
                          {failH > 0 && (
                            <div
                              className="w-full max-w-[20px] rounded-t bg-destructive"
                              style={{ height: `${failH}%`, minHeight: failH > 0 ? '2px' : 0 }}
                            />
                          )}
                          {passH > 0 && (
                            <div
                              className={cn("w-full max-w-[20px] bg-success", failH === 0 ? 'rounded-t' : '')}
                              style={{ height: `${passH}%`, minHeight: passH > 0 ? '2px' : 0 }}
                            />
                          )}
                        </div>
                        <span className="text-[10px] text-muted-foreground mt-1">{monthLabel}</span>
                      </div>
                    )
                  })}
                </div>
                <div className="mt-3 flex gap-4 text-sm">
                  <span className="flex items-center gap-2">
                    <span className="w-3 h-3 rounded-full bg-success" /> Passed
                  </span>
                  <span className="flex items-center gap-2">
                    <span className="w-3 h-3 rounded-full bg-destructive" /> Failed
                  </span>
                </div>
              </>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Recent Activity Row */}
      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <h2 className="text-lg font-semibold text-foreground">
              Recent Assessments
            </h2>
            <p className="text-sm text-muted-foreground">
              Latest competency assessments
            </p>
          </CardHeader>
          <CardContent>
            {loading ? (
              <div className="space-y-3">
                {[1, 2, 3].map((i) => (
                  <div key={i} className="h-12 rounded-lg bg-muted/50 animate-pulse" />
                ))}
              </div>
            ) : assessments.length === 0 ? (
              <p className="text-sm text-muted-foreground py-8 text-center">
                No recent assessments.
              </p>
            ) : (
              <ul className="space-y-2">
                {assessments.map((a) => (
                  <li
                    key={a.id}
                    className={cn(
                      "flex items-center gap-3 p-3 rounded-lg border border-border",
                      "hover:bg-muted/30 cursor-pointer transition-colors"
                    )}
                    onClick={() => navigate(`/workforce/assessments/${a.id}/execute`)}
                  >
                    <ClipboardCheck className="w-4 h-4 text-muted-foreground shrink-0" />
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-foreground truncate">
                        {a.title || a.reference_number}
                      </p>
                      <p className="text-xs text-muted-foreground capitalize">
                        {a.status?.replace(/_/g, ' ')}
                      </p>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        {/* Quick actions */}
        <Card>
          <CardHeader>
            <h2 className="text-lg font-semibold text-foreground">Quick Actions</h2>
            <p className="text-sm text-muted-foreground">Common workforce actions</p>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-3">
              <button
                onClick={() => navigate('/workforce/assessments/new')}
                className="flex flex-col items-center gap-2 p-4 rounded-lg border border-border hover:bg-muted/30 transition-colors"
              >
                <ClipboardCheck className="w-6 h-6 text-primary" />
                <span className="text-sm font-medium text-foreground">New Assessment</span>
              </button>
              <button
                onClick={() => navigate('/workforce/training/new')}
                className="flex flex-col items-center gap-2 p-4 rounded-lg border border-border hover:bg-muted/30 transition-colors"
              >
                <BookOpen className="w-6 h-6 text-primary" />
                <span className="text-sm font-medium text-foreground">New Induction</span>
              </button>
              <button
                onClick={() => navigate('/workforce/engineers')}
                className="flex flex-col items-center gap-2 p-4 rounded-lg border border-border hover:bg-muted/30 transition-colors"
              >
                <Users className="w-6 h-6 text-primary" />
                <span className="text-sm font-medium text-foreground">Engineer Directory</span>
              </button>
              <button
                onClick={() => navigate('/workforce/calendar')}
                className="flex flex-col items-center gap-2 p-4 rounded-lg border border-border hover:bg-muted/30 transition-colors"
              >
                <Clock className="w-6 h-6 text-primary" />
                <span className="text-sm font-medium text-foreground">Schedule</span>
              </button>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
