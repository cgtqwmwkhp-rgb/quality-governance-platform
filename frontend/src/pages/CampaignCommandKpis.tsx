import { useCallback, useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Loader2 } from 'lucide-react'
import {
  documentCampaignApi,
  getApiErrorMessage,
  type ComplianceOverviewResponse,
} from '../api/client'
import { Button } from '../components/ui/Button'

function formatShortDate(isoDate: string): string {
  const date = new Date(`${isoDate}T00:00:00`)
  if (Number.isNaN(date.getTime())) return isoDate
  return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

interface CampaignCommandKpisProps {
  className?: string
}

export function CampaignCommandKpis({ className }: CampaignCommandKpisProps) {
  const { t } = useTranslation()
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [overview, setOverview] = useState<ComplianceOverviewResponse | null>(null)

  const loadOverview = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await documentCampaignApi.getComplianceOverview()
      setOverview(response.data)
    } catch (err) {
      setOverview(null)
      setError(getApiErrorMessage(err, t('campaigns.command.overview_load_error')))
    } finally {
      setLoading(false)
    }
  }, [t])

  useEffect(() => {
    void loadOverview()
  }, [loadOverview])

  const maxSeriesCompleted = useMemo(() => {
    if (!overview?.series?.length) return 0
    return Math.max(...overview.series.map((point) => point.completed), 0)
  }, [overview])

  const kpis = overview
    ? [
        {
          label: t('campaigns.command.kpi_active', 'Active campaigns'),
          value: String(overview.active_campaigns),
        },
        {
          label: t('campaigns.command.kpi_completion', 'Completion'),
          value: `${Math.round(overview.overall_completion_rate)}%`,
        },
        {
          label: t('campaigns.command.kpi_overdue', 'Overdue'),
          value: String(overview.overdue_count),
        },
        {
          label: t('campaigns.command.kpi_quiz_fail', 'Quiz fails'),
          value: String(overview.quiz_fail_count),
        },
        {
          label: t('campaigns.command.kpi_open_rate', 'Open rate'),
          value: `${Math.round(overview.open_rate)}%`,
        },
      ]
    : []

  return (
    <div className={className} data-testid="campaign-command-kpis">
      {loading ? (
        <div className="flex justify-center py-6">
          <Loader2 className="h-6 w-6 animate-spin text-primary" />
        </div>
      ) : error ? (
        <div
          role="alert"
          className="rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive"
        >
          {error}
          <Button variant="link" size="sm" className="ml-2 h-auto p-0" onClick={() => void loadOverview()}>
            {t('common.retry', 'Retry')}
          </Button>
        </div>
      ) : overview ? (
        <div className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
            {kpis.map((kpi) => (
              <div key={kpi.label} className="rounded-lg border border-border bg-card px-3 py-2">
                <p className="text-xs text-muted-foreground">{kpi.label}</p>
                <p className="text-lg font-semibold text-foreground">{kpi.value}</p>
              </div>
            ))}
          </div>

          <div>
            <p className="mb-2 text-sm font-medium text-foreground">
              {t('campaigns.command.trend_title', '14-day completions trend')}
            </p>
            {overview.series.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                {t('campaigns.command.trend_empty', 'No daily activity recorded yet.')}
              </p>
            ) : (
              <ul className="space-y-1" data-testid="campaign-command-trend">
                {overview.series.map((point) => {
                  const widthPct =
                    maxSeriesCompleted > 0
                      ? Math.max(4, Math.round((point.completed / maxSeriesCompleted) * 100))
                      : 0
                  return (
                    <li
                      key={point.date}
                      className="grid grid-cols-[4.5rem_1fr_5rem] items-center gap-2 text-xs"
                    >
                      <span className="text-muted-foreground">{formatShortDate(point.date)}</span>
                      <div className="h-2 rounded bg-muted">
                        <div
                          className="h-2 rounded bg-primary"
                          style={{ width: `${widthPct}%` }}
                          title={t('campaigns.command.trend_completed', {
                            defaultValue: '{{count}} completed',
                            count: point.completed,
                          })}
                        />
                      </div>
                      <span className="text-right text-muted-foreground">
                        {t('campaigns.command.trend_day_summary', {
                          defaultValue: '{{completed}} done · {{opened}} opened · {{overdue}} overdue',
                          completed: point.completed,
                          opened: point.opened,
                          overdue: point.overdue,
                        })}
                      </span>
                    </li>
                  )
                })}
              </ul>
            )}
          </div>
        </div>
      ) : null}
    </div>
  )
}
