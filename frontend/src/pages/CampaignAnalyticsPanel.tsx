import { useCallback, useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Loader2 } from 'lucide-react'
import {
  documentCampaignApi,
  getApiErrorMessage,
  type CampaignAnalyticsResponse,
  type ScoreHistogramBucket,
} from '../api/client'
import { Button } from '../components/ui/Button'
import { EmptyState } from '../components/ui'

const SCORE_BUCKETS: ScoreHistogramBucket[] = ['0-19', '20-39', '40-59', '60-79', '80-100']

interface CampaignAnalyticsPanelProps {
  campaignId: number
  compact?: boolean
}

function formatHours(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return '—'
  if (value < 24) return `${Math.round(value)}h`
  return `${(value / 24).toFixed(1)}d`
}

export function CampaignAnalyticsPanel({ campaignId, compact = false }: CampaignAnalyticsPanelProps) {
  const { t } = useTranslation()
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [analytics, setAnalytics] = useState<CampaignAnalyticsResponse | null>(null)

  const loadAnalytics = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await documentCampaignApi.getCampaignAnalytics(campaignId)
      setAnalytics(response.data)
    } catch (err) {
      setAnalytics(null)
      setError(getApiErrorMessage(err, t('campaigns.analytics.load_error', 'Could not load analytics')))
    } finally {
      setLoading(false)
    }
  }, [campaignId, t])

  useEffect(() => {
    void loadAnalytics()
  }, [loadAnalytics])

  const histogramMax = useMemo(() => {
    if (!analytics?.score_histogram?.length) return 0
    return Math.max(...analytics.score_histogram.map((bucket) => bucket.count), 0)
  }, [analytics])

  const attemptsMax = useMemo(() => {
    if (!analytics?.attempts_distribution?.length) return 0
    return Math.max(...analytics.attempts_distribution.map((row) => row.count), 0)
  }, [analytics])

  if (loading && !analytics) {
    return (
      <div className="flex justify-center py-6" data-testid="campaign-analytics-panel">
        <Loader2 className="h-6 w-6 animate-spin text-primary" />
      </div>
    )
  }

  if (error && !analytics) {
    return (
      <div
        role="alert"
        className="rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive"
        data-testid="campaign-analytics-panel"
      >
        {error}
        <Button variant="link" size="sm" className="ml-2 h-auto p-0" onClick={() => void loadAnalytics()}>
          {t('common.retry', 'Retry')}
        </Button>
      </div>
    )
  }

  if (!analytics) {
    return null
  }

  const funnelSteps = [
    { label: t('campaigns.analytics.funnel_assigned', 'Assigned'), value: analytics.funnel.assigned },
    { label: t('campaigns.analytics.funnel_opened', 'Opened'), value: analytics.funnel.opened },
    {
      label: t('campaigns.analytics.funnel_quiz_attempted', 'Quiz attempted'),
      value: analytics.funnel.quiz_attempted,
    },
    {
      label: t('campaigns.analytics.funnel_quiz_passed', 'Quiz passed'),
      value: analytics.funnel.quiz_passed,
    },
    { label: t('campaigns.analytics.funnel_completed', 'Completed'), value: analytics.funnel.completed },
  ]

  const histogramByBucket = new Map(analytics.score_histogram.map((row) => [row.bucket, row.count]))

  return (
    <div className="space-y-4" data-testid="campaign-analytics-panel">
      <div>
        <p className="mb-2 text-sm font-medium text-foreground">
          {t('campaigns.analytics.funnel_title', 'Completion funnel')}
        </p>
        <div className={`grid gap-2 ${compact ? 'grid-cols-2 md:grid-cols-5' : 'grid-cols-2 md:grid-cols-5'}`}>
          {funnelSteps.map((step) => (
            <div key={step.label} className="rounded-lg border border-border bg-card px-3 py-2">
              <p className="text-xs text-muted-foreground">{step.label}</p>
              <p className="text-lg font-semibold text-foreground">{step.value}</p>
            </div>
          ))}
        </div>
      </div>

      {analytics.require_quiz ? (
        <div className="grid gap-4 md:grid-cols-2">
          <div>
            <p className="mb-2 text-sm font-medium text-foreground">
              {t('campaigns.analytics.score_histogram_title', 'Quiz score distribution')}
            </p>
            {histogramMax === 0 ? (
              <EmptyState
                title={t('campaigns.analytics.score_empty_title', 'No quiz scores yet')}
                description={t(
                  'campaigns.analytics.score_empty_desc',
                  'Scores appear after assignees submit the quiz.',
                )}
              />
            ) : (
              <ul className="space-y-2" data-testid="campaign-analytics-histogram">
                {SCORE_BUCKETS.map((bucket) => {
                  const count = histogramByBucket.get(bucket) ?? 0
                  const widthPct = histogramMax > 0 ? Math.max(4, Math.round((count / histogramMax) * 100)) : 0
                  return (
                    <li key={bucket} className="grid grid-cols-[3.5rem_1fr_2rem] items-center gap-2 text-xs">
                      <span className="text-muted-foreground">{bucket}</span>
                      <div className="h-2 rounded bg-muted">
                        <div className="h-2 rounded bg-primary" style={{ width: `${widthPct}%` }} />
                      </div>
                      <span className="text-right text-foreground">{count}</span>
                    </li>
                  )
                })}
              </ul>
            )}
          </div>

          <div>
            <p className="mb-2 text-sm font-medium text-foreground">
              {t('campaigns.analytics.attempts_title', 'Quiz attempts')}
            </p>
            {attemptsMax === 0 ? (
              <p className="text-sm text-muted-foreground">
                {t('campaigns.analytics.attempts_empty', 'No quiz attempts recorded yet.')}
              </p>
            ) : (
              <ul className="space-y-2" data-testid="campaign-analytics-attempts">
                {analytics.attempts_distribution.map((row) => {
                  const widthPct = attemptsMax > 0 ? Math.max(4, Math.round((row.count / attemptsMax) * 100)) : 0
                  const label =
                    row.attempts >= 3
                      ? t('campaigns.analytics.attempts_3plus', '3+ attempts')
                      : t('campaigns.analytics.attempts_n', {
                          defaultValue: '{{count}} attempts',
                          count: row.attempts,
                        })
                  return (
                    <li key={row.attempts} className="grid grid-cols-[5rem_1fr_2rem] items-center gap-2 text-xs">
                      <span className="text-muted-foreground">{label}</span>
                      <div className="h-2 rounded bg-muted">
                        <div className="h-2 rounded bg-primary" style={{ width: `${widthPct}%` }} />
                      </div>
                      <span className="text-right text-foreground">{row.count}</span>
                    </li>
                  )
                })}
              </ul>
            )}

            <div className="mt-4 grid grid-cols-2 gap-3 text-sm">
              <div className="rounded-lg border border-border bg-card px-3 py-2">
                <p className="text-xs text-muted-foreground">
                  {t('campaigns.analytics.time_p50', 'Median time to complete')}
                </p>
                <p className="font-semibold text-foreground">
                  {formatHours(analytics.time_to_complete_hours.p50)}
                </p>
              </div>
              <div className="rounded-lg border border-border bg-card px-3 py-2">
                <p className="text-xs text-muted-foreground">
                  {t('campaigns.analytics.time_p90', 'P90 time to complete')}
                </p>
                <p className="font-semibold text-foreground">
                  {formatHours(analytics.time_to_complete_hours.p90)}
                </p>
              </div>
            </div>
          </div>
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">
          {t('campaigns.analytics.no_quiz', 'This campaign does not require a quiz.')}
        </p>
      )}

      <p className="text-xs text-muted-foreground">
        {t('campaigns.analytics.reminders_total', {
          defaultValue: '{{count}} reminders sent',
          count: analytics.reminder_sent_total,
        })}
      </p>
    </div>
  )
}
