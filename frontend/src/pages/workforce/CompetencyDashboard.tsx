import { useState, useEffect, useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import { Users, Award, Clock, AlertTriangle, TrendingUp, ClipboardCheck, BookOpen } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { workforceApi } from '../../api/client'
import { Card, CardContent, CardHeader } from '../../components/ui/Card'
import { cn } from '../../helpers/utils'

const KPI_CARDS = [
  { key: 'engineers', labelKey: 'workforce.competency.total_engineers', icon: Users, color: 'text-primary' },
  { key: 'active', labelKey: 'workforce.competency.active_competencies', icon: Award, color: 'text-success' },
  { key: 'expiring', labelKey: 'workforce.competency.expiring_soon', icon: Clock, color: 'text-warning' },
  { key: 'overdue', labelKey: 'workforce.competency.overdue', icon: AlertTriangle, color: 'text-destructive' },
]

const STATUS_COLORS: Record<string, string> = {
  active: 'bg-success',
  due: 'bg-warning',
  expired: 'bg-destructive',
  failed: 'bg-destructive/60',
  not_assessed: 'bg-muted-foreground/40',
}

const STATUS_LABEL_KEYS: Record<string, string> = {
  active: 'workforce.competency.current',
  due: 'workforce.competency.expiring_soon',
  expired: 'workforce.competency.expired',
  failed: 'workforce.competency.failed',
  not_assessed: 'workforce.competency.not_assessed',
}

type TrendMonth = { month: string | null; total: number; passed: number; failed: number }

export default function CompetencyDashboard() {
  const { t } = useTranslation()
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
        <h1 className="text-2xl font-bold text-foreground">{t('workforce.competency_dashboard.title')}</h1>
        <p className="text-muted-foreground mt-1">
          {t('workforce.competency_dashboard.subtitle')}
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {KPI_CARDS.map((k) => (
          <Card key={k.key} hoverable>
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-muted-foreground">{t(k.labelKey)}</p>
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
              {t('workforce.competency.status_breakdown')}
            </h2>
            <p className="text-sm text-muted-foreground">
              {compTotal} {t('workforce.competency.total_records')}
            </p>
          </CardHeader>
          <CardContent>
            {compTotal === 0 ? (
              <div className="flex flex-col items-center justify-center h-48 text-muted-foreground gap-2">
                <Award className="w-10 h-10" />
                <p className="text-sm">{t('workforce.competency.no_data')}</p>
                <p className="text-xs">{t('workforce.competency.no_data_description')}</p>
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
                            {STATUS_LABEL_KEYS[state] ? t(STATUS_LABEL_KEYS[state]) : state.replace(/_/g, ' ')}
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
              {Object.entries(STATUS_LABEL_KEYS).map(([key, labelKey]) => (
                <span key={key} className="flex items-center gap-2">
                  <span className={cn("w-3 h-3 rounded-full", STATUS_COLORS[key])} />
                  {t(labelKey)}
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
                <h2 className="text-lg font-semibold text-foreground">{t('workforce.competency.assessment_trends')}</h2>
                <p className="text-sm text-muted-foreground">{t('workforce.competency.assessment_trends_subtitle')}</p>
              </div>
              <TrendingUp className="w-5 h-5 text-muted-foreground" />
            </div>
          </CardHeader>
          <CardContent>
            {trends.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-48 text-muted-foreground gap-2">
                <TrendingUp className="w-10 h-10" />
                <p className="text-sm">{t('workforce.competency.no_trend_data')}</p>
                <p className="text-xs">{t('workforce.competency.trend_description')}</p>
              </div>
            ) : (
              <>
                <div className="flex items-end gap-1 h-40">
                  {trends.map((tr, i) => {
                    const passH = (tr.passed / trendMax) * 100
                    const failH = (tr.failed / trendMax) * 100
                    const monthLabel = tr.month
                      ? new Date(tr.month).toLocaleDateString('en-GB', { month: 'short' })
                      : ''
                    return (
                      <div key={i} className="flex-1 flex flex-col items-center gap-0.5" title={`${monthLabel}: ${tr.total} total, ${tr.passed} passed, ${tr.failed} failed`}>
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
                    <span className="w-3 h-3 rounded-full bg-success" /> {t('workforce.competency.passed')}
                  </span>
                  <span className="flex items-center gap-2">
                    <span className="w-3 h-3 rounded-full bg-destructive" /> {t('workforce.competency.failed')}
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
              {t('workforce.competency.recent_assessments')}
            </h2>
            <p className="text-sm text-muted-foreground">
              {t('workforce.competency.latest_assessments')}
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
                {t('workforce.competency.no_recent')}
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
                    onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); navigate(`/workforce/assessments/${a.id}/execute`); } }}
                    role="button"
                    tabIndex={0}
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
            <h2 className="text-lg font-semibold text-foreground">{t('workforce.competency.quick_actions')}</h2>
            <p className="text-sm text-muted-foreground">{t('workforce.competency.common_actions')}</p>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-3">
              <button
                onClick={() => navigate('/workforce/assessments/new')}
                className="flex flex-col items-center gap-2 p-4 rounded-lg border border-border hover:bg-muted/30 transition-colors"
              >
                <ClipboardCheck className="w-6 h-6 text-primary" />
                <span className="text-sm font-medium text-foreground">{t('workforce.assessments.new')}</span>
              </button>
              <button
                onClick={() => navigate('/workforce/training/new')}
                className="flex flex-col items-center gap-2 p-4 rounded-lg border border-border hover:bg-muted/30 transition-colors"
              >
                <BookOpen className="w-6 h-6 text-primary" />
                <span className="text-sm font-medium text-foreground">{t('workforce.induction.new')}</span>
              </button>
              <button
                onClick={() => navigate('/workforce/engineers')}
                className="flex flex-col items-center gap-2 p-4 rounded-lg border border-border hover:bg-muted/30 transition-colors"
              >
                <Users className="w-6 h-6 text-primary" />
                <span className="text-sm font-medium text-foreground">{t('workforce.competency.engineer_directory')}</span>
              </button>
              <button
                onClick={() => navigate('/workforce/calendar')}
                className="flex flex-col items-center gap-2 p-4 rounded-lg border border-border hover:bg-muted/30 transition-colors"
              >
                <Clock className="w-6 h-6 text-primary" />
                <span className="text-sm font-medium text-foreground">{t('workforce.competency.schedule')}</span>
              </button>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
