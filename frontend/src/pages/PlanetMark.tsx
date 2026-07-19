import { useCallback, useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import {
  Leaf,
  RefreshCw,
  XCircle,
  Plus,
  Download,
  Award,
  Loader2,
} from 'lucide-react'
import { useTranslation } from 'react-i18next'
import {
  planetMarkApi,
  ErrorClass,
  createApiError,
  getApiErrorMessage,
  isSetupRequired,
  type SetupRequiredResponse,
} from '../api/client'
import type {
  PlanetMarkDashboardResponse,
  PlanetMarkReportingYearRecord,
  PlanetMarkActionRecord,
  PlanetMarkScope3Response,
} from '../api/planetMarkClient'
import { SetupRequiredPanel } from '../components/ui/SetupRequiredPanel'
import { EmptyState } from '../components/ui/EmptyState'
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { LoadingSkeleton } from '../components/ui/LoadingSkeleton'
import { ActionCard, type ActionItem } from '../components/planet-mark/ActionCard'
import { ActionSummaryKPIs } from '../components/planet-mark/ActionSummaryKPIs'
import { cn } from '../helpers/utils'
import {
  PLANET_MARK_SECTIONS,
  buildHotspotInitiatives,
  buildPlanetMarkTrendsViewModel,
  buildPlanetMarkYearsViewModel,
  findPriorReportingYear,
  formatDeltaPercent,
  formatEmissions,
  hasPositiveCarbonTotal,
  initiativeToCreateActionPayload,
  parsePlanetMarkSection,
  resolveSelectedYearId,
  sortReportingYearsDesc,
  type PlanetMarkHotspotInitiative,
} from './planetMarkHelpers'
import { buildMonthlyEvidenceHonestyViewModel } from './planetMarkMonthlyEvidenceHonesty'
import { PlanetMarkYearEvidencePanel } from './planetMarkYearEvidencePanel'
import { PlanetMarkYearOcrPanel } from './planetMarkYearOcrPanel'
import { PlanetMarkYearXlsxIngestPanel } from './planetMarkYearXlsxIngestPanel'
import {
  PLANET_MARK_YEAR_CERT_DOC_TYPES,
  latestEvidenceIdForType,
} from './planetMarkYearEvidenceHelpers'
import type { PlanetMarkEvidenceRecord } from '../api/planetMarkClient'

type LoadState = 'idle' | 'loading' | 'success' | 'error' | 'setup_required'

function toActionItem(action: PlanetMarkActionRecord): ActionItem {
  return {
    id: action.id,
    action_id: action.action_id,
    action_title: action.action_title,
    owner: action.owner || 'Unassigned',
    deadline: action.deadline,
    status: action.status,
    progress_percent: action.progress_percent ?? 0,
    target_scope: action.target_scope ?? undefined,
    expected_reduction_pct: action.expected_reduction_pct ?? 0,
    is_overdue: action.is_overdue,
    notes: null,
  }
}

export default function PlanetMark() {
  const { t } = useTranslation()
  const [searchParams, setSearchParams] = useSearchParams()
  const section = parsePlanetMarkSection(searchParams.get('section'))
  const yearParam = searchParams.get('year')

  const now = new Date()
  const defaultYear = now.getUTCFullYear()

  const [years, setYears] = useState<PlanetMarkReportingYearRecord[]>([])
  const [dashboard, setDashboard] = useState<PlanetMarkDashboardResponse | null>(null)
  const [actions, setActions] = useState<PlanetMarkActionRecord[]>([])
  const [actionsSummary, setActionsSummary] = useState<{
    total: number
    completed: number
    in_progress: number
    overdue: number
    not_started: number
    completion_rate_percent: number
    avg_progress_percent: number
  } | null>(null)
  const [loadState, setLoadState] = useState<LoadState>('idle')
  const [sectionLoading, setSectionLoading] = useState(false)
  const [errorClass, setErrorClass] = useState<ErrorClass | null>(null)
  const [setupRequired, setSetupRequired] = useState<SetupRequiredResponse | null>(null)
  const [setupActionError, setSetupActionError] = useState<string | null>(null)
  const [scope3Current, setScope3Current] = useState<PlanetMarkScope3Response | null>(null)
  const [scope3Prior, setScope3Prior] = useState<PlanetMarkScope3Response | null>(null)
  const [trendsLoading, setTrendsLoading] = useState(false)
  const [creatingInitiativeId, setCreatingInitiativeId] = useState<string | null>(null)
  const [initiativeError, setInitiativeError] = useState<string | null>(null)
  const [exportLoadingFormat, setExportLoadingFormat] = useState<'json' | 'xlsx' | null>(null)
  const [exportError, setExportError] = useState<string | null>(null)
  const [isCreatingYear, setIsCreatingYear] = useState(false)
  const [yearEvidence, setYearEvidence] = useState<PlanetMarkEvidenceRecord[]>([])
  const [setupYearForm, setSetupYearForm] = useState({
    year_label: `YE${defaultYear}`,
    year_number: defaultYear,
    period_start: `${defaultYear}-01-01`,
    period_end: `${defaultYear}-12-31`,
    average_fte: '1',
    organization_name: 'Plantexpand Limited',
    is_baseline_year: false,
    reduction_target_percent: '5',
  })

  const selectedYearId = useMemo(
    () => resolveSelectedYearId(years, yearParam),
    [years, yearParam],
  )
  const selectedYear = useMemo(
    () => years.find((y) => y.id === selectedYearId) ?? null,
    [years, selectedYearId],
  )
  const trendsVm = useMemo(
    () =>
      buildPlanetMarkTrendsViewModel({
        dashboard,
        years,
        selectedYearId,
        scope3Current,
        scope3Prior,
      }),
    [dashboard, years, selectedYearId, scope3Current, scope3Prior],
  )
  const yearsVm = useMemo(
    () => buildPlanetMarkYearsViewModel({ years, selectedYearId }),
    [years, selectedYearId],
  )
  const initiatives = useMemo(
    () => buildHotspotInitiatives(scope3Current),
    [scope3Current],
  )

  const setQuery = useCallback(
    (patch: Record<string, string | null>) => {
      const next = new URLSearchParams(searchParams)
      Object.entries(patch).forEach(([key, value]) => {
        if (value == null || value === '' || (key === 'section' && value === 'years')) {
          if (key === 'section' && value === 'years') next.delete(key)
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

  const loadImproveData = useCallback(async (yearId: number) => {
    const [actionsRes, summaryRes] = await Promise.allSettled([
      planetMarkApi.listActions(yearId),
      planetMarkApi.getActionsSummary(yearId),
    ])
    if (actionsRes.status === 'fulfilled') {
      setActions(actionsRes.value.data.actions ?? [])
    } else {
      setActions([])
    }
    if (summaryRes.status === 'fulfilled') {
      setActionsSummary(summaryRes.value.data)
    } else {
      setActionsSummary(null)
    }
  }, [])

  const loadData = useCallback(async (isRetry = false) => {
    setLoadState('loading')
    setErrorClass(null)
    setSetupRequired(null)
    setSetupActionError(null)

    try {
      const [dashboardResponse, yearsResponse] = await Promise.all([
        planetMarkApi.getDashboard(),
        planetMarkApi.listYears(),
      ])
      const dashboardPayload = dashboardResponse.data
      const yearsPayload = yearsResponse.data

      if (isSetupRequired(dashboardPayload)) {
        setSetupRequired(dashboardPayload)
        setLoadState('setup_required')
        return
      }
      if (isSetupRequired(yearsPayload)) {
        setSetupRequired(yearsPayload)
        setLoadState('setup_required')
        return
      }

      setDashboard(dashboardPayload as PlanetMarkDashboardResponse)
      const sorted = sortReportingYearsDesc(yearsPayload.years ?? [])
      setYears(sorted)
      setLoadState('success')
    } catch (err) {
      const apiError = createApiError(err)
      setErrorClass(apiError.error_class)
      if (
        !isRetry &&
        (apiError.error_class === ErrorClass.NETWORK_ERROR ||
          apiError.error_class === ErrorClass.SERVER_ERROR)
      ) {
        await loadData(true)
        return
      }
      setLoadState('error')
    }
  }, [])

  useEffect(() => {
    void loadData()
  }, [loadData])

  useEffect(() => {
    const needsScope3 = section === 'trends' || section === 'improve' || section === 'export'
    if (!selectedYearId || !needsScope3) {
      if (section !== 'trends' && section !== 'improve' && section !== 'export') {
        setScope3Current(null)
        setScope3Prior(null)
      }
      return
    }

    const priorYear = section === 'trends' ? findPriorReportingYear(years, selectedYearId) : null

    let cancelled = false
    const run = async () => {
      if (section === 'trends') setTrendsLoading(true)
      try {
        const [currentRes, priorRes] = await Promise.allSettled([
          planetMarkApi.getScope3(selectedYearId),
          priorYear ? planetMarkApi.getScope3(priorYear.id) : Promise.resolve(null),
        ])
        if (cancelled) return
        setScope3Current(currentRes.status === 'fulfilled' ? currentRes.value.data : null)
        setScope3Prior(
          priorRes.status === 'fulfilled' && priorRes.value ? priorRes.value.data : null,
        )
      } finally {
        if (!cancelled && section === 'trends') setTrendsLoading(false)
      }
    }
    void run()
    return () => {
      cancelled = true
    }
  }, [selectedYearId, section, years])

  useEffect(() => {
    if (!selectedYearId || (section !== 'improve' && section !== 'export')) {
      if (section !== 'improve' && section !== 'export') {
        setActions([])
        setActionsSummary(null)
      }
      return
    }
    let cancelled = false
    const run = async () => {
      if (section === 'improve') setSectionLoading(true)
      try {
        await loadImproveData(selectedYearId)
      } finally {
        if (!cancelled && section === 'improve') setSectionLoading(false)
      }
    }
    void run()
    return () => {
      cancelled = true
    }
  }, [selectedYearId, section, loadImproveData])

  useEffect(() => {
    if (years.length === 0 || yearParam) return
    const defaultId = years[0]?.id
    if (defaultId != null) {
      setQuery({ year: String(defaultId) })
    }
  }, [years, yearParam, setQuery])


  const handleExportPack = async (format: 'json' | 'xlsx') => {
    if (!selectedYear) return
    setExportLoadingFormat(format)
    setExportError(null)
    try {
      await planetMarkApi.downloadExportPack(selectedYear.id, format)
    } catch (err) {
      setExportError(getApiErrorMessage(err, t('planet_mark.shell.export_failed')))
    } finally {
      setExportLoadingFormat(null)
    }
  }

  const handleAddInitiative = async (initiative: PlanetMarkHotspotInitiative) => {
    if (!selectedYear) return
    setCreatingInitiativeId(initiative.id)
    setInitiativeError(null)
    try {
      await planetMarkApi.createAction(
        selectedYear.id,
        initiativeToCreateActionPayload(initiative),
      )
      await loadImproveData(selectedYear.id)
    } catch (err) {
      setInitiativeError(getApiErrorMessage(err, t('planet_mark.shell.initiatives.add_failed')))
    } finally {
      setCreatingInitiativeId(null)
    }
  }


  const handleCreateReportingYear = async (event: React.FormEvent) => {
    event.preventDefault()
    setSetupActionError(null)

    const averageFte = Number(setupYearForm.average_fte)
    const reductionTarget = Number(setupYearForm.reduction_target_percent)
    if (!setupYearForm.year_label.trim()) {
      setSetupActionError(t('planet_mark.shell.setup.label_required'))
      return
    }
    if (!setupYearForm.period_start || !setupYearForm.period_end) {
      setSetupActionError(t('planet_mark.shell.setup.period_required'))
      return
    }
    if (setupYearForm.period_end < setupYearForm.period_start) {
      setSetupActionError(t('planet_mark.shell.setup.period_order'))
      return
    }
    if (!Number.isFinite(averageFte) || averageFte <= 0) {
      setSetupActionError(t('planet_mark.shell.setup.fte_required'))
      return
    }
    if (!Number.isFinite(reductionTarget) || reductionTarget < 0) {
      setSetupActionError(t('planet_mark.shell.setup.target_required'))
      return
    }

    setIsCreatingYear(true)
    try {
      await planetMarkApi.createReportingYear({
        year_label: setupYearForm.year_label.trim(),
        year_number: Number(setupYearForm.year_number),
        period_start: `${setupYearForm.period_start}T00:00:00.000Z`,
        period_end: `${setupYearForm.period_end}T23:59:59.000Z`,
        average_fte: averageFte,
        organization_name: setupYearForm.organization_name.trim() || 'Plantexpand Limited',
        is_baseline_year: setupYearForm.is_baseline_year,
        reduction_target_percent: reductionTarget,
      })
      await loadData()
    } catch (err) {
      const apiError = createApiError(err)
      setErrorClass(apiError.error_class)
      setSetupActionError(apiError.detail || t('planet_mark.shell.setup.create_failed'))
    } finally {
      setIsCreatingYear(false)
    }
  }

  const renderSetupForm = () =>
    setupRequired?.next_action.includes('/api/v1/planet-mark/years') ? (
      <Card className="mt-8 max-w-lg mx-auto">
        <CardHeader>
          <CardTitle>{t('planet_mark.shell.setup.title')}</CardTitle>
          <p className="text-sm text-muted-foreground">{t('planet_mark.shell.setup.subtitle')}</p>
        </CardHeader>
        <CardContent>
          <form className="space-y-4" onSubmit={handleCreateReportingYear}>
            <div className="grid gap-4 sm:grid-cols-2">
              <label className="space-y-2 text-sm text-foreground">
                <span className="font-medium">{t('planet_mark.shell.setup.year_label')}</span>
                <input
                  className="w-full rounded-lg border border-border bg-background px-3 py-2"
                  value={setupYearForm.year_label}
                  onChange={(e) =>
                    setSetupYearForm((prev) => ({ ...prev, year_label: e.target.value }))
                  }
                />
              </label>
              <label className="space-y-2 text-sm text-foreground">
                <span className="font-medium">{t('planet_mark.shell.setup.year_number')}</span>
                <input
                  type="number"
                  min="1"
                  className="w-full rounded-lg border border-border bg-background px-3 py-2"
                  value={setupYearForm.year_number}
                  onChange={(e) =>
                    setSetupYearForm((prev) => ({
                      ...prev,
                      year_number: Number(e.target.value) || defaultYear,
                    }))
                  }
                />
              </label>
            </div>
            {setupActionError ? (
              <div className="rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                {setupActionError}
              </div>
            ) : null}
            <Button type="submit" disabled={isCreatingYear} className="w-full">
              {isCreatingYear
                ? t('planet_mark.shell.setup.creating')
                : t('planet_mark.shell.setup.submit')}
            </Button>
          </form>
        </CardContent>
      </Card>
    ) : null

  if (loadState === 'setup_required' && setupRequired) {
    return (
      <div className="space-y-6 animate-fade-in p-6">
        <header className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div className="flex items-center gap-4">
            <div className="p-3 bg-primary/10 rounded-xl">
              <Leaf className="w-8 h-8 text-primary" />
            </div>
            <div>
              <h1 className="text-3xl font-bold text-foreground">{t('planet_mark.title')}</h1>
              <p className="text-muted-foreground">{t('planet_mark.subtitle')}</p>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2" data-testid="planet-mark-filters">
            <select
              aria-label={t('planet_mark.shell.year_switcher_label')}
              data-testid="planet-mark-year-filter"
              className="rounded-lg border border-border bg-card px-3 py-2 text-sm font-medium text-foreground"
              defaultValue=""
            >
              <option value="">{t('planet_mark.shell.no_years', 'No reporting years')}</option>
            </select>
            <Button type="button" variant="outline" size="sm" data-testid="planet-mark-filter-apply">
              Filter
            </Button>
          </div>
        </header>
        <SetupRequiredPanel response={setupRequired} onRetry={() => void loadData()} />
        {renderSetupForm()}
      </div>
    )
  }

  if (loadState === 'loading') {
    return (
      <div className="p-6">
        <LoadingSkeleton variant="table" rows={5} columns={4} />
      </div>
    )
  }

  if (loadState === 'error') {
    return (
      <div className="p-6">
        <EmptyState
          icon={<XCircle className="w-8 h-8 text-destructive" />}
          title={t('planet_mark.failed_to_load')}
          description={
            errorClass === ErrorClass.NETWORK_ERROR
              ? t('planet_mark.error_network')
              : errorClass === ErrorClass.SERVER_ERROR
                ? t('planet_mark.error_server')
                : errorClass === ErrorClass.AUTH_ERROR
                  ? t('planet_mark.error_auth')
                  : errorClass === ErrorClass.NOT_FOUND
                    ? t('planet_mark.error_not_found')
                    : t('planet_mark.error_unknown')
          }
          action={
            <Button onClick={() => void loadData()}>
              <RefreshCw className="w-4 h-4" />
              {t('planet_mark.try_again')}
            </Button>
          }
        />
      </div>
    )
  }

  return (
    <div className="space-y-6 animate-fade-in p-6">
      <header className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
        <div className="flex items-center gap-4">
          <div className="p-3 bg-primary/10 rounded-xl">
            <Leaf className="w-8 h-8 text-primary" />
          </div>
          <div>
            <h1 className="text-3xl font-bold text-foreground">{t('planet_mark.title')}</h1>
            <p className="text-muted-foreground mt-1">{t('planet_mark.shell.page_subtitle')}</p>
          </div>
        </div>
        <div
          className="flex flex-col sm:flex-row sm:items-center gap-2"
          data-testid="planet-mark-filters"
        >
          <label htmlFor="planet-mark-year" className="text-sm font-medium text-muted-foreground">
            {t('planet_mark.shell.year_switcher_label')}
          </label>
          <select
            id="planet-mark-year"
            value={selectedYear?.id ?? ''}
            onChange={(e) => setQuery({ year: e.target.value || null })}
            aria-label={t('planet_mark.shell.year_switcher_label')}
            data-testid="planet-mark-year-filter"
            className="rounded-lg border border-border bg-card px-3 py-2 text-sm font-medium text-foreground"
          >
            {years.length === 0 ? (
              <option value="">{t('planet_mark.shell.no_years', 'No reporting years')}</option>
            ) : (
              years.map((y) => (
                <option key={y.id} value={y.id}>
                  {y.year_label}
                  {y.is_baseline ? ` (${t('planet_mark.baseline')})` : ''}
                </option>
              ))
            )}
          </select>
          <select
            value={section}
            onChange={(e) => setQuery({ section: e.target.value === 'years' ? null : e.target.value })}
            aria-label={t('planet_mark.shell.tabs_aria')}
            data-testid="planet-mark-section-filter"
            className="rounded-lg border border-border bg-card px-3 py-2 text-sm font-medium text-foreground"
          >
            {PLANET_MARK_SECTIONS.map(({ id, labelKey }) => (
              <option key={id} value={id}>
                {t(labelKey)}
              </option>
            ))}
          </select>
          <Button type="button" variant="outline" size="sm" data-testid="planet-mark-filter-apply">
            Filter
          </Button>
        </div>
      </header>

      <div
        className="flex bg-surface rounded-xl p-1 border border-border overflow-x-auto"
        role="tablist"
        aria-label={t('planet_mark.shell.tabs_aria')}
      >
        {PLANET_MARK_SECTIONS.map(({ id, labelKey, icon: Icon }) => (
          <button
            key={id}
            type="button"
            role="tab"
            aria-selected={section === id}
            onClick={() => setQuery({ section: id === 'years' ? null : id })}
            className={cn(
              'flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200 whitespace-nowrap',
              section === id
                ? 'bg-primary text-primary-foreground shadow-sm'
                : 'text-muted-foreground hover:text-foreground',
            )}
          >
            <Icon className="w-4 h-4" />
            {t(labelKey)}
          </button>
        ))}
      </div>

      {years.length === 0 ? (
        <Card>
          <CardContent>
            <EmptyState
              icon={<Leaf className="w-8 h-8 text-muted-foreground" />}
              title={t('planet_mark.no_data')}
              description={t('planet_mark.no_data_description')}
              action={
                <Button onClick={() => void loadData()}>
                  <Plus className="w-4 h-4" />
                  {t('planet_mark.add_reporting_year')}
                </Button>
              }
            />
          </CardContent>
        </Card>
      ) : (
        <>
          {section === 'years' && selectedYear && (
            <div className="space-y-4" data-testid="planet-mark-section-years">
              <Card>
                <CardHeader>
                  <CardTitle>{selectedYear.year_label}</CardTitle>
                  <p className="text-sm text-muted-foreground">{selectedYear.period}</p>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <div className="rounded-lg border border-border bg-surface/50 p-4">
                      <p className="text-xs text-muted-foreground">{t('planet_mark.tco2e_total')}</p>
                      <p className="text-2xl font-bold text-foreground">
                        {formatEmissions(
                          hasPositiveCarbonTotal(selectedYear.total_emissions)
                            ? selectedYear.total_emissions
                            : null,
                        )}
                      </p>
                    </div>
                    <div className="rounded-lg border border-border bg-surface/50 p-4">
                      <p className="text-xs text-muted-foreground">{t('planet_mark.tco2e_fte')}</p>
                      <p className="text-2xl font-bold text-foreground">
                        {formatEmissions(
                          hasPositiveCarbonTotal(selectedYear.emissions_per_fte)
                            ? selectedYear.emissions_per_fte
                            : null,
                          2,
                        )}
                      </p>
                    </div>
                    <div className="rounded-lg border border-border bg-surface/50 p-4">
                      <p className="text-xs text-muted-foreground">{t('planet_mark.data_quality')}</p>
                      <p className="text-2xl font-bold text-foreground">
                        {selectedYear.data_quality != null ? `${selectedYear.data_quality}/16` : '—'}
                      </p>
                    </div>
                    <div className="rounded-lg border border-border bg-surface/50 p-4">
                      <p className="text-xs text-muted-foreground">
                        {t('planet_mark.certification_status')}
                      </p>
                      <p className="text-lg font-semibold text-foreground capitalize flex items-center gap-2">
                        {selectedYear.certification_status === 'certified' && (
                          <Award className="w-4 h-4 text-success" />
                        )}
                        {selectedYear.certification_status || '—'}
                      </p>
                    </div>
                  </div>
                </CardContent>
              </Card>

              <PlanetMarkYearEvidencePanel
                yearId={selectedYear.id}
                yearLabel={selectedYear.year_label}
                onEvidenceChange={setYearEvidence}
              />

              <PlanetMarkYearOcrPanel
                yearId={selectedYear.id}
                yearLabel={selectedYear.year_label}
                measurementReportEvidenceId={latestEvidenceIdForType(
                  yearEvidence,
                  PLANET_MARK_YEAR_CERT_DOC_TYPES.measurementReport,
                )}
                certificateEvidenceId={latestEvidenceIdForType(
                  yearEvidence,
                  PLANET_MARK_YEAR_CERT_DOC_TYPES.certificate,
                )}
                onApplied={async () => {
                  await loadData()
                }}
              />

              {yearsVm.showMsXlsxIngestPanel && (
                <PlanetMarkYearXlsxIngestPanel
                  yearId={selectedYear.id}
                  yearLabel={selectedYear.year_label}
                  hasIngestedCarbon={yearsVm.selectedHasIngestedCarbon}
                  currentTotal={
                    hasPositiveCarbonTotal(selectedYear.total_emissions)
                      ? selectedYear.total_emissions
                      : null
                  }
                  currentPerFte={
                    hasPositiveCarbonTotal(selectedYear.emissions_per_fte)
                      ? selectedYear.emissions_per_fte
                      : null
                  }
                  onIngested={async () => {
                    await loadData()
                  }}
                />
              )}

              <Card>
                <CardHeader>
                  <CardTitle>{t('planet_mark.shell.all_years_title')}</CardTitle>
                  <p className="text-sm text-muted-foreground">
                    {t('planet_mark.shell.years.all_years_hint')}
                  </p>
                </CardHeader>
                <CardContent className="divide-y divide-border">
                  {yearsVm.allYearRows.map((year) => (
                    <button
                      key={year.id}
                      type="button"
                      onClick={() => setQuery({ year: String(year.id), section: null })}
                      className={cn(
                        'w-full flex items-center justify-between py-3 text-left hover:bg-surface/50 px-2 rounded-lg transition-colors',
                        year.id === selectedYear.id && 'bg-primary/5',
                      )}
                    >
                      <div>
                        <p className="font-medium text-foreground">{year.label}</p>
                        <p className="text-sm text-muted-foreground">{year.period}</p>
                      </div>
                      <p className="text-sm text-muted-foreground">
                        {year.hasIngestedCarbon && year.total != null
                          ? `${formatEmissions(year.total)} tCO₂e`
                          : t('planet_mark.shell.no_emissions_recorded')}
                      </p>
                    </button>
                  ))}
                </CardContent>
              </Card>

              {yearsVm.priorYearsWithoutIngest.length > 0 && (
                <Card data-testid="planet-mark-years-prior-empty">
                  <CardHeader>
                    <CardTitle>{t('planet_mark.shell.years.prior_empty_title')}</CardTitle>
                    <p className="text-sm text-muted-foreground">
                      {t('planet_mark.shell.years.prior_empty_hint')}
                    </p>
                  </CardHeader>
                  <CardContent className="divide-y divide-border">
                    {yearsVm.priorYearsWithoutIngest.map((year) => (
                      <div
                        key={year.id}
                        className="flex items-center justify-between py-3 text-sm"
                      >
                        <div>
                          <p className="font-medium text-foreground">{year.label}</p>
                          <p className="text-muted-foreground">{year.period}</p>
                        </div>
                        <span className="text-muted-foreground">
                          {t('planet_mark.shell.no_emissions_recorded')}
                        </span>
                      </div>
                    ))}
                  </CardContent>
                </Card>
              )}
            </div>
          )}

          {section === 'trends' && (
            <div className="space-y-4" data-testid="planet-mark-section-trends">
              {trendsLoading && trendsVm.isEmpty ? (
                <div className="flex items-center gap-2 text-muted-foreground py-8 justify-center">
                  <Loader2 className="w-5 h-5 animate-spin" />
                  {t('planet_mark.loading')}
                </div>
              ) : trendsVm.isEmpty ? (
                <Card>
                  <CardContent>
                    <EmptyState
                      title={t('planet_mark.shell.empty.trends')}
                      description={t('planet_mark.shell.empty.trends_desc')}
                    />
                  </CardContent>
                </Card>
              ) : (
                <>
                  {trendsVm.showComparativePanels && trendsVm.yoyPerFtePercent != null && (
                    <Card data-testid="planet-mark-trends-yoy">
                      <CardHeader>
                        <CardTitle>{t('planet_mark.shell.trends.yoy_title')}</CardTitle>
                        <p className="text-sm text-muted-foreground">
                          {t('planet_mark.shell.trends.yoy_hint')}
                        </p>
                      </CardHeader>
                      <CardContent>
                        <p
                          className={cn(
                            'text-3xl font-bold',
                            trendsVm.yoyPerFtePercent <= 0 ? 'text-success' : 'text-destructive',
                          )}
                        >
                          {formatDeltaPercent(trendsVm.yoyPerFtePercent)}
                        </p>
                        <p className="text-sm text-muted-foreground mt-1">
                          {t('planet_mark.shell.trends.yoy_per_fte')}
                        </p>
                      </CardContent>
                    </Card>
                  )}

                  {trendsVm.showHistoricalTable && (
                    <Card data-testid="planet-mark-trends-historical">
                      <CardHeader>
                        <CardTitle>{t('planet_mark.shell.section.trends')}</CardTitle>
                        <p className="text-sm text-muted-foreground">
                          {t('planet_mark.shell.trends_live_hint')}
                        </p>
                      </CardHeader>
                      <CardContent className="overflow-x-auto">
                        <table className="w-full text-sm">
                          <thead>
                            <tr className="border-b border-border text-left text-muted-foreground">
                              <th className="py-2 pr-4">{t('planet_mark.shell.trends.year')}</th>
                              <th className="py-2 pr-4">{t('planet_mark.tco2e_total')}</th>
                              <th className="py-2 pr-4">{t('planet_mark.tco2e_fte')}</th>
                              <th className="py-2 pr-4">{t('planet_mark.shell.trends.yoy_total')}</th>
                              <th className="py-2">{t('planet_mark.shell.trends.yoy_per_fte_col')}</th>
                            </tr>
                          </thead>
                          <tbody>
                            {trendsVm.historicalRows.map((row) => (
                              <tr key={row.label} className="border-b border-border/60">
                                <td className="py-3 font-medium text-foreground">{row.label}</td>
                                <td className="py-3 text-foreground">
                                  {formatEmissions(row.total)}
                                </td>
                                <td className="py-3 text-foreground">
                                  {formatEmissions(row.perFte, 2)}
                                </td>
                                <td className="py-3 text-foreground">
                                  {formatDeltaPercent(row.yoyTotalPercent)}
                                </td>
                                <td className="py-3 text-foreground">
                                  {formatDeltaPercent(row.yoyPerFtePercent)}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </CardContent>
                    </Card>
                  )}

                  {trendsVm.showComparativePanels &&
                    trendsVm.scopeDeltas.some(
                      (delta) =>
                        hasPositiveCarbonTotal(delta.current) &&
                        hasPositiveCarbonTotal(delta.prior),
                    ) && (
                      <Card data-testid="planet-mark-trends-scope">
                        <CardHeader>
                          <CardTitle>{t('planet_mark.shell.trends.scope_title')}</CardTitle>
                          <p className="text-sm text-muted-foreground">
                            {t('planet_mark.shell.trends.scope_hint')}
                          </p>
                        </CardHeader>
                        <CardContent className="overflow-x-auto">
                          <table className="w-full text-sm">
                            <thead>
                              <tr className="border-b border-border text-left text-muted-foreground">
                                <th className="py-2 pr-4">{t('planet_mark.shell.trends.scope')}</th>
                                <th className="py-2 pr-4">{t('planet_mark.shell.trends.current')}</th>
                                <th className="py-2 pr-4">{t('planet_mark.shell.trends.prior')}</th>
                                <th className="py-2">{t('planet_mark.shell.trends.delta')}</th>
                              </tr>
                            </thead>
                            <tbody>
                              {trendsVm.scopeDeltas.map((delta) => (
                                <tr key={delta.scopeKey} className="border-b border-border/60">
                                  <td className="py-3 font-medium text-foreground">
                                    {t(delta.labelKey)}
                                  </td>
                                  <td className="py-3 text-foreground">
                                    {formatEmissions(delta.current)}
                                  </td>
                                  <td className="py-3 text-foreground">
                                    {formatEmissions(delta.prior)}
                                  </td>
                                  <td className="py-3 text-foreground">
                                    {formatDeltaPercent(delta.deltaPercent)}
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </CardContent>
                      </Card>
                    )}

                  {trendsVm.showComparativePanels && trendsVm.categoryDeltas.length > 0 && (
                    <Card data-testid="planet-mark-trends-category">
                      <CardHeader>
                        <CardTitle>{t('planet_mark.shell.trends.category_title')}</CardTitle>
                        <p className="text-sm text-muted-foreground">
                          {t('planet_mark.shell.trends.category_hint')}
                        </p>
                      </CardHeader>
                      <CardContent className="overflow-x-auto">
                        <table className="w-full text-sm">
                          <thead>
                            <tr className="border-b border-border text-left text-muted-foreground">
                              <th className="py-2 pr-4">{t('planet_mark.shell.trends.category')}</th>
                              <th className="py-2 pr-4">{t('planet_mark.shell.trends.current')}</th>
                              <th className="py-2 pr-4">{t('planet_mark.shell.trends.prior')}</th>
                              <th className="py-2">{t('planet_mark.shell.trends.delta')}</th>
                            </tr>
                          </thead>
                          <tbody>
                            {trendsVm.categoryDeltas.map((delta) => (
                              <tr
                                key={`${delta.number}-${delta.name}`}
                                className="border-b border-border/60"
                              >
                                <td className="py-3 font-medium text-foreground">
                                  {delta.number}. {delta.name}
                                </td>
                                <td className="py-3 text-foreground">
                                  {formatEmissions(delta.current)}
                                </td>
                                <td className="py-3 text-foreground">
                                  {formatEmissions(delta.prior)}
                                </td>
                                <td className="py-3 text-foreground">
                                  {formatDeltaPercent(delta.deltaPercent)}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </CardContent>
                    </Card>
                  )}

                  {trendsVm.showThinPriorYear && (
                    <Card data-testid="planet-mark-trends-thin-prior">
                      <CardHeader>
                        <CardTitle>{t('planet_mark.shell.trends.prior_years_title')}</CardTitle>
                        <p className="text-sm text-muted-foreground">
                          {t('planet_mark.shell.trends.prior_years_hint')}
                        </p>
                      </CardHeader>
                      <CardContent className="divide-y divide-border">
                        {trendsVm.thinPriorYears.map((year) => (
                          <div
                            key={year.label}
                            className="flex items-center justify-between py-3 text-sm"
                          >
                            <span className="font-medium text-foreground">{year.label}</span>
                            <span className="text-muted-foreground">
                              {year.total != null || year.perFte != null
                                ? t('planet_mark.shell.trends.prior_year_summary', {
                                    total: formatEmissions(year.total),
                                    perFte: formatEmissions(year.perFte, 2),
                                  })
                                : t('planet_mark.shell.no_emissions_recorded')}
                            </span>
                          </div>
                        ))}
                      </CardContent>
                    </Card>
                  )}
                </>
              )}
            </div>
          )}

          {section === 'monthly' && (
            <div className="space-y-4" data-testid="planet-mark-section-monthly">
              {(() => {
                const monthlyHonesty = buildMonthlyEvidenceHonestyViewModel({
                  hasSelectedYear: Boolean(selectedYear),
                })
                return (
                  <>
                    <Card data-testid="planet-mark-monthly-e4-panel">
                      <CardHeader>
                        <CardTitle>{t('planet_mark.shell.monthly_e4.title')}</CardTitle>
                        <p
                          className="text-sm text-muted-foreground"
                          data-testid="planet-mark-monthly-e4-honesty"
                        >
                          {t('planet_mark.shell.monthly_e4.honesty')}
                        </p>
                      </CardHeader>
                      <CardContent className="space-y-3">
                        <ul className="space-y-2" data-testid="planet-mark-monthly-e4-capabilities">
                          {monthlyHonesty.capabilities.map((row) => (
                            <li
                              key={row.id}
                              className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-border px-3 py-2 text-sm"
                              data-testid={`planet-mark-monthly-e4-cap-${row.id}`}
                            >
                              <span className="text-foreground">
                                {t(`planet_mark.shell.monthly_e4.cap.${row.id}`)}
                              </span>
                              <span className="text-xs text-muted-foreground">
                                {t(`planet_mark.shell.monthly_e4.status.${row.status}`)}
                              </span>
                            </li>
                          ))}
                        </ul>
                        <p
                          className="text-xs text-muted-foreground"
                          data-testid="planet-mark-monthly-e4-forecast"
                        >
                          {t('planet_mark.shell.monthly_e4.forecast_followon')}
                        </p>
                      </CardContent>
                    </Card>
                    <Card>
                      <CardContent>
                        {monthlyHonesty.showSelectYearPrompt ? (
                          <EmptyState
                            title={t('planet_mark.shell.monthly_e4.select_year_title')}
                            description={t('planet_mark.shell.monthly_e4.select_year_desc')}
                          />
                        ) : (
                          <EmptyState
                            title={t('planet_mark.shell.empty.monthly')}
                            description={t('planet_mark.shell.empty.monthly_desc')}
                          />
                        )}
                      </CardContent>
                    </Card>
                  </>
                )
              })()}
            </div>
          )}

          {section === 'improve' && selectedYear && (
            <div className="space-y-4" data-testid="planet-mark-section-improve">
              {sectionLoading ? (
                <div className="flex items-center gap-2 text-muted-foreground py-8 justify-center">
                  <Loader2 className="w-5 h-5 animate-spin" />
                  {t('planet_mark.loading')}
                </div>
              ) : (
                <>
                  <Card data-testid="planet-mark-initiatives">
                    <CardHeader>
                      <CardTitle>{t('planet_mark.shell.initiatives.title')}</CardTitle>
                      <p className="text-sm text-muted-foreground">
                        {t('planet_mark.shell.initiatives.hint')}
                      </p>
                    </CardHeader>
                    <CardContent className="space-y-3">
                      {initiatives.length === 0 ? (
                        <EmptyState
                          title={t('planet_mark.shell.initiatives.empty')}
                          description={t('planet_mark.shell.initiatives.empty_desc')}
                        />
                      ) : (
                        <>
                          {initiativeError ? (
                            <p className="text-sm text-destructive" role="alert" data-testid="planet-mark-initiative-error">
                              {initiativeError}
                            </p>
                          ) : null}
                          <ul className="space-y-3">
                            {initiatives.map((initiative) => (
                              <li
                                key={initiative.id}
                                className="rounded-lg border border-border p-3 flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between"
                                data-testid={`planet-mark-initiative-${initiative.id}`}
                              >
                                <div className="min-w-0 space-y-1">
                                  <p className="font-medium text-foreground">{initiative.title}</p>
                                  <p className="text-xs text-muted-foreground">
                                    {t('planet_mark.shell.initiatives.footprint', {
                                      percent: initiative.footprintPercent.toFixed(1),
                                      tonnes: formatEmissions(initiative.currentCo2e),
                                    })}
                                  </p>
                                  <p className="text-xs text-muted-foreground">{initiative.measurable}</p>
                                </div>
                                <Button
                                  size="sm"
                                  variant="outline"
                                  disabled={creatingInitiativeId === initiative.id}
                                  data-testid={`planet-mark-initiative-add-${initiative.id}`}
                                  onClick={() => void handleAddInitiative(initiative)}
                                >
                                  {creatingInitiativeId === initiative.id ? (
                                    <Loader2 className="w-4 h-4 animate-spin" />
                                  ) : (
                                    <Plus className="w-4 h-4" />
                                  )}
                                  {t('planet_mark.shell.initiatives.add_action')}
                                </Button>
                              </li>
                            ))}
                          </ul>
                        </>
                      )}
                    </CardContent>
                  </Card>

                  {actions.length === 0 ? (
                    <Card>
                      <CardContent>
                        <EmptyState
                          title={t('planet_mark.shell.empty.improve')}
                          description={t('planet_mark.shell.empty.improve_desc')}
                        />
                      </CardContent>
                    </Card>
                  ) : (
                    <>
                      {actionsSummary && <ActionSummaryKPIs summary={actionsSummary} />}
                      <div className="space-y-2">
                        {actions.map((action) => (
                          <ActionCard
                            key={action.id}
                            yearId={selectedYear.id}
                            action={toActionItem(action)}
                            selected={false}
                            onSelect={() => {}}
                            onUpdated={() => void loadImproveData(selectedYear.id)}
                          />
                        ))}
                      </div>
                    </>
                  )}
                </>
              )}
            </div>
          )}

          {section === 'export' && (
            <div data-testid="planet-mark-section-export">
              <Card>
                <CardHeader>
                  <CardTitle>{t('planet_mark.shell.section.export')}</CardTitle>
                  <p className="text-sm text-muted-foreground">
                    {t('planet_mark.shell.export_hint')}
                  </p>
                </CardHeader>
                <CardContent>
                  {selectedYear ? (
                    <div className="flex flex-col gap-4">
                      <p className="text-sm text-muted-foreground" data-testid="planet-mark-export-honesty">
                        {t('planet_mark.shell.export_honesty')}
                      </p>
                      {exportError ? (
                        <p className="text-sm text-destructive" data-testid="planet-mark-export-error">
                          {exportError}
                        </p>
                      ) : null}
                      <div className="flex flex-col sm:flex-row sm:items-center gap-4">
                        <p className="text-sm text-muted-foreground flex-1">
                          {t('planet_mark.shell.export_ready', { year: selectedYear.year_label })}
                        </p>
                        <div className="flex flex-wrap gap-2">
                          <Button
                            variant="outline"
                            data-testid="planet-mark-export-json"
                            disabled={exportLoadingFormat != null}
                            onClick={() => void handleExportPack('json')}
                          >
                            {exportLoadingFormat === 'json' ? (
                              <Loader2 className="w-4 h-4 animate-spin" />
                            ) : (
                              <Download className="w-4 h-4" />
                            )}
                            {t('planet_mark.export_json')}
                          </Button>
                          <Button
                            variant="outline"
                            data-testid="planet-mark-export-xlsx"
                            disabled={exportLoadingFormat != null}
                            onClick={() => void handleExportPack('xlsx')}
                          >
                            {exportLoadingFormat === 'xlsx' ? (
                              <Loader2 className="w-4 h-4 animate-spin" />
                            ) : (
                              <Download className="w-4 h-4" />
                            )}
                            {t('planet_mark.export_xlsx')}
                          </Button>
                        </div>
                      </div>
                    </div>
                  ) : (
                    <EmptyState
                      title={t('planet_mark.shell.empty.export')}
                      description={t('planet_mark.shell.empty.export_desc')}
                    />
                  )}
                </CardContent>
              </Card>
            </div>
          )}
        </>
      )}
    </div>
  )
}
