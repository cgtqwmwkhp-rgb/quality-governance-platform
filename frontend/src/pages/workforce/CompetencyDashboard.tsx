import { useCallback, useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import {
  AlertTriangle,
  Award,
  Clock,
  Loader2,
  Users,
  XCircle,
  HelpCircle,
} from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { getApiErrorMessage, workforceApi, type WdpEngineerMatrix } from '../../api/client'
import { Button } from '../../components/ui/Button'
import { Card, CardContent, CardHeader } from '../../components/ui/Card'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../../components/ui/Select'
import { cn } from '../../helpers/utils'

const MATRIX_STATUSES = ['active', 'due', 'expired', 'failed', 'not_assessed'] as const
type MatrixStatus = (typeof MATRIX_STATUSES)[number]

const DUE_BAND_KEYS = ['due_30', 'due_60', 'due_90'] as const

const STATUS_COLORS: Record<string, string> = {
  active: 'bg-success',
  due: 'bg-warning',
  expired: 'bg-destructive',
  failed: 'bg-destructive/60',
  not_assessed: 'bg-muted-foreground/40',
}

const STATUS_LABEL_KEYS: Record<string, string> = {
  active: 'workforce.competency.active_competencies',
  due: 'workforce.competency.due',
  due_30: 'workforce.competency.due_30',
  due_60: 'workforce.competency.due_60',
  due_90: 'workforce.competency.due_90',
  expired: 'workforce.competency.expired',
  failed: 'workforce.competency.failed',
  not_assessed: 'workforce.competency.not_assessed',
}

type KpiValue = number | null

type KpiDef = {
  key: string
  labelKey: string
  icon: typeof Users
  color: string
}

function formatKpi(value: KpiValue): string {
  return value == null ? '—' : String(value)
}

function cellStatus(
  competencies: Record<number, string> | Record<string, string>,
  assetTypeId: number,
): string {
  const map = competencies as Record<string | number, string>
  return map[assetTypeId] ?? map[String(assetTypeId)] ?? 'not_assessed'
}

function pickCount(source: Record<string, number> | undefined, key: string): number {
  return source?.[key] ?? 0
}

export default function CompetencyDashboard() {
  const { t } = useTranslation()
  const navigate = useNavigate()

  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [summaryUnavailable, setSummaryUnavailable] = useState(false)
  const [matrixUnavailable, setMatrixUnavailable] = useState(false)

  const [engineersTotal, setEngineersTotal] = useState<KpiValue>(null)
  const [competencyCounts, setCompetencyCounts] = useState<Record<string, number> | null>(null)
  const [matrix, setMatrix] = useState<WdpEngineerMatrix | null>(null)
  const [statusFilter, setStatusFilter] = useState<string>('all')

  const load = useCallback(async () => {
    setLoading(true)
    setLoadError(null)
    setSummaryUnavailable(false)
    setMatrixUnavailable(false)

    const [summaryResult, matrixResult] = await Promise.allSettled([
      workforceApi.analytics.getSummary(),
      workforceApi.analytics.getEngineerMatrix(),
    ])

    let summaryOk = false
    let matrixOk = false

    if (summaryResult.status === 'fulfilled') {
      summaryOk = true
      const s = summaryResult.value.data
      setEngineersTotal(s?.engineers?.total ?? 0)
      setCompetencyCounts(s?.competencies ?? {})
    } else {
      setSummaryUnavailable(true)
      setEngineersTotal(null)
      setCompetencyCounts(null)
    }

    if (matrixResult.status === 'fulfilled') {
      matrixOk = true
      setMatrix(matrixResult.value.data ?? { asset_types: [], engineers: [] })
    } else {
      setMatrixUnavailable(true)
      setMatrix(null)
    }

    if (!summaryOk && !matrixOk) {
      const err =
        summaryResult.status === 'rejected'
          ? summaryResult.reason
          : matrixResult.status === 'rejected'
            ? matrixResult.reason
            : null
      setLoadError(
        getApiErrorMessage(err, t('workforce.competency.load_failed_body')),
      )
    }

    setLoading(false)
  }, [t])

  useEffect(() => {
    void load()
  }, [load])

  const dueBandsPresent = useMemo(() => {
    if (!competencyCounts) return [] as (typeof DUE_BAND_KEYS)[number][]
    return DUE_BAND_KEYS.filter((k) => typeof competencyCounts[k] === 'number')
  }, [competencyCounts])

  const kpiCards: KpiDef[] = useMemo(() => {
    const cards: KpiDef[] = [
      {
        key: 'engineers',
        labelKey: 'workforce.competency.engineers',
        icon: Users,
        color: 'text-primary',
      },
      {
        key: 'active',
        labelKey: 'workforce.competency.active_competencies',
        icon: Award,
        color: 'text-success',
      },
    ]

    if (dueBandsPresent.length > 0) {
      for (const band of dueBandsPresent) {
        cards.push({
          key: band,
          labelKey: STATUS_LABEL_KEYS[band],
          icon: Clock,
          color: 'text-warning',
        })
      }
    } else {
      cards.push({
        key: 'due',
        labelKey: 'workforce.competency.due',
        icon: Clock,
        color: 'text-warning',
      })
    }

    cards.push(
      {
        key: 'expired',
        labelKey: 'workforce.competency.expired',
        icon: AlertTriangle,
        color: 'text-destructive',
      },
      {
        key: 'failed',
        labelKey: 'workforce.competency.failed',
        icon: XCircle,
        color: 'text-destructive',
      },
      {
        key: 'not_assessed',
        labelKey: 'workforce.competency.not_assessed',
        icon: HelpCircle,
        color: 'text-muted-foreground',
      },
    )

    return cards
  }, [dueBandsPresent])

  const kpiValues = useMemo(() => {
    const values: Record<string, KpiValue> = {}
    if (summaryUnavailable || competencyCounts == null) {
      for (const card of kpiCards) values[card.key] = null
      values.engineers = engineersTotal
      return values
    }
    values.engineers = engineersTotal
    values.active = pickCount(competencyCounts, 'active')
    values.due = pickCount(competencyCounts, 'due')
    values.expired = pickCount(competencyCounts, 'expired')
    values.failed = pickCount(competencyCounts, 'failed')
    values.not_assessed = pickCount(competencyCounts, 'not_assessed')
    for (const band of dueBandsPresent) {
      values[band] = pickCount(competencyCounts, band)
    }
    return values
  }, [competencyCounts, dueBandsPresent, engineersTotal, kpiCards, summaryUnavailable])

  const filteredEngineers = useMemo(() => {
    if (!matrix) return []
    if (statusFilter === 'all') return matrix.engineers
    return matrix.engineers.filter((eng) =>
      Object.values(eng.competencies).some((status) => status === statusFilter),
    )
  }, [matrix, statusFilter])

  const matrixEmpty =
    !matrixUnavailable &&
    matrix != null &&
    (matrix.engineers.length === 0 || matrix.asset_types.length === 0)

  const filterEmpty =
    !matrixUnavailable &&
    matrix != null &&
    matrix.engineers.length > 0 &&
    matrix.asset_types.length > 0 &&
    filteredEngineers.length === 0

  if (loading) {
    return (
      <div
        className="flex items-center justify-center h-64"
        data-testid="competency-dashboard-loading"
      >
        <Loader2 className="w-8 h-8 text-primary animate-spin" aria-label="Loading" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-foreground">
            {t('workforce.competency.title')}
          </h1>
          <p className="text-muted-foreground mt-1">{t('workforce.competency.subtitle')}</p>
        </div>
        <div className="space-y-1.5 min-w-[12rem]">
          <label
            htmlFor="competency-status-filter"
            className="text-xs font-medium text-muted-foreground"
          >
            {t('workforce.competency.filter_status')}
          </label>
          <Select value={statusFilter} onValueChange={setStatusFilter}>
            <SelectTrigger
              id="competency-status-filter"
              aria-label={t('workforce.competency.filter_status')}
              data-testid="competency-status-filter"
            >
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">{t('workforce.competency.filter_all')}</SelectItem>
              {MATRIX_STATUSES.map((status) => (
                <SelectItem key={status} value={status}>
                  {t(STATUS_LABEL_KEYS[status])}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      {loadError ? (
        <div
          className="rounded-lg border border-destructive/40 bg-destructive/10 px-4 py-3 text-sm text-destructive"
          role="alert"
          data-testid="competency-dashboard-load-error"
        >
          <p className="font-medium">{t('workforce.competency.load_failed')}</p>
          <p className="mt-1">{loadError}</p>
          <p className="mt-1 text-destructive/90">{t('workforce.competency.load_failed_body')}</p>
          <Button
            size="sm"
            variant="secondary"
            className="mt-3"
            onClick={() => void load()}
            data-testid="competency-dashboard-retry"
          >
            {t('common.retry')}
          </Button>
        </div>
      ) : null}

      {!loadError && (summaryUnavailable || matrixUnavailable) ? (
        <div
          className="rounded-lg border border-warning/40 bg-warning/10 px-4 py-3 text-sm"
          role="status"
          data-testid="competency-dashboard-partial"
        >
          <p className="font-medium text-foreground">
            {t('workforce.competency.partial_title')}
          </p>
          <ul className="mt-1 list-disc pl-5 text-muted-foreground">
            {summaryUnavailable ? (
              <li>{t('workforce.competency.partial_summary')}</li>
            ) : null}
            {matrixUnavailable ? (
              <li>{t('workforce.competency.matrix_unavailable')}</li>
            ) : null}
          </ul>
          <Button
            size="sm"
            variant="secondary"
            className="mt-3"
            onClick={() => void load()}
            data-testid="competency-dashboard-retry-partial"
          >
            {t('common.retry')}
          </Button>
        </div>
      ) : null}

      <div
        className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6"
        data-testid="competency-kpi-row"
      >
        {kpiCards.map((k) => {
          const value = kpiValues[k.key]
          const unavailable = value == null
          return (
            <Card key={k.key} hoverable>
              <CardContent className="p-4">
                <div className="flex items-center justify-between gap-2">
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-muted-foreground truncate">
                      {unavailable
                        ? `${t(k.labelKey)} (${t('workforce.competency.kpi_unavailable')})`
                        : t(k.labelKey)}
                    </p>
                    <p
                      className="text-2xl font-bold text-foreground mt-1"
                      data-testid={`competency-kpi-${k.key}`}
                      aria-label={
                        unavailable
                          ? `${t(k.labelKey)} ${t('workforce.competency.kpi_unavailable')}`
                          : undefined
                      }
                    >
                      {formatKpi(value)}
                    </p>
                  </div>
                  <div className={cn('p-2 rounded-lg bg-muted shrink-0', k.color)}>
                    <k.icon className="w-5 h-5" />
                  </div>
                </div>
              </CardContent>
            </Card>
          )
        })}
      </div>

      <Card data-testid="competency-skills-matrix">
        <CardHeader>
          <h2 className="text-lg font-semibold text-foreground">
            {t('workforce.competency.skills_matrix')}
          </h2>
          <p className="text-sm text-muted-foreground">
            {t('workforce.competency.skills_matrix_subtitle')}
          </p>
        </CardHeader>
        <CardContent>
          {matrixUnavailable ? (
            <div
              className="flex flex-col items-center justify-center h-48 text-muted-foreground gap-2"
              data-testid="competency-matrix-unavailable"
            >
              <AlertTriangle className="w-10 h-10 text-destructive" />
              <p className="text-sm font-medium text-foreground">
                {t('workforce.competency.matrix_unavailable')}
              </p>
              <p className="text-xs">{t('workforce.competency.load_failed_body')}</p>
              <Button size="sm" variant="secondary" onClick={() => void load()}>
                {t('common.retry')}
              </Button>
            </div>
          ) : matrixEmpty ? (
            <div
              className="flex flex-col items-center justify-center h-48 text-muted-foreground gap-2"
              data-testid="competency-matrix-empty"
            >
              <Award className="w-10 h-10" />
              <p className="text-sm">{t('workforce.competency.skills_matrix_empty')}</p>
              <p className="text-xs">{t('workforce.competency.no_data_description')}</p>
            </div>
          ) : filterEmpty ? (
            <div
              className="flex flex-col items-center justify-center h-48 text-muted-foreground gap-2"
              data-testid="competency-matrix-filter-empty"
            >
              <Award className="w-10 h-10" />
              <p className="text-sm">{t('workforce.competency.empty_filter')}</p>
            </div>
          ) : (
            <div className="overflow-x-auto" data-testid="competency-matrix-grid">
              <table className="w-full border-collapse text-sm">
                <thead>
                  <tr>
                    <th className="sticky left-0 z-10 bg-card text-left p-2 font-medium text-muted-foreground border-b border-border min-w-[8rem]">
                      {t('workforce.competency.engineers')}
                    </th>
                    {matrix!.asset_types.map((at) => (
                      <th
                        key={at.id}
                        className="p-2 font-medium text-muted-foreground border-b border-border text-center whitespace-nowrap"
                        title={at.category}
                      >
                        {at.name}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {filteredEngineers.map((eng) => (
                    <tr key={eng.engineer_id} className="hover:bg-muted/20">
                      <th
                        scope="row"
                        className="sticky left-0 z-10 bg-card text-left p-2 font-medium text-foreground border-b border-border whitespace-nowrap"
                      >
                        <button
                          type="button"
                          className="text-primary hover:underline text-left"
                          onClick={() => navigate(`/workforce/engineers/${eng.engineer_id}`)}
                          data-testid={`competency-engineer-${eng.engineer_id}`}
                        >
                          {eng.employee_number || `#${eng.engineer_id}`}
                        </button>
                      </th>
                      {matrix!.asset_types.map((at) => {
                        const status = cellStatus(eng.competencies, at.id) as MatrixStatus | string
                        const dimmed =
                          statusFilter !== 'all' && status !== statusFilter
                        return (
                          <td
                            key={at.id}
                            className="p-1.5 border-b border-border text-center"
                          >
                            <button
                              type="button"
                              title={`${eng.employee_number || eng.engineer_id} · ${at.name}: ${status}`}
                              aria-label={`${eng.employee_number || eng.engineer_id} ${at.name} ${status}`}
                              className={cn(
                                'mx-auto block h-6 w-6 rounded-sm transition-opacity focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                                STATUS_COLORS[status] ?? 'bg-muted',
                                dimmed && 'opacity-25',
                              )}
                              data-testid={`competency-cell-${eng.engineer_id}-${at.id}`}
                              data-status={status}
                              onClick={() =>
                                navigate(`/workforce/engineers/${eng.engineer_id}`)
                              }
                            />
                          </td>
                        )
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
              <div className="mt-4 flex flex-wrap gap-4 text-sm">
                {MATRIX_STATUSES.map((status) => (
                  <span key={status} className="flex items-center gap-2">
                    <span className={cn('w-3 h-3 rounded-sm', STATUS_COLORS[status])} />
                    {t(STATUS_LABEL_KEYS[status])}
                  </span>
                ))}
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
