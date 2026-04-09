import { useState, useEffect, useCallback } from 'react'
import {
  Leaf,
  BarChart3,
  Target,
  CheckCircle2,
  AlertTriangle,
  Clock,
  Fuel,
  Zap,
  Trash2,
  Users,
  Building2,
  RefreshCw,
  Plus,
  Download,
  Award,
  Gauge,
  Factory,
  Truck,
  ShoppingCart,
  Briefcase,
  Home,
  Globe,
  XCircle,
  ClipboardCheck,
  ArrowUpRight,
  FileUp,
} from 'lucide-react'
import { useTranslation } from 'react-i18next'
import {
  planetMarkApi,
  externalAuditRecordsApi,
  ErrorClass,
  createApiError,
  isSetupRequired,
  SetupRequiredResponse,
  type ExternalAuditRecordSummary,
} from '../api/client'
import { SetupRequiredPanel } from '../components/ui/SetupRequiredPanel'
import { EvidenceUploadRow } from '../components/planet-mark/EvidenceUploadRow'
import { CertificationStatusPanel } from '../components/planet-mark/CertificationStatusPanel'
import { ActionCard, type ActionItem } from '../components/planet-mark/ActionCard'
import { ActionSummaryKPIs } from '../components/planet-mark/ActionSummaryKPIs'
import { ActionImportModal } from '../components/planet-mark/ActionImportModal'

interface ReportingYear {
  id: number
  year_label: string
  year_number: number
  period: string
  total_emissions: number
  emissions_per_fte: number
  fte: number
  scope_1: number
  scope_2: number
  scope_3: number
  data_quality: number
  certification_status: string
  is_baseline: boolean
}

interface ImprovementAction {
  id: number
  action_id: string
  action_title: string
  owner: string
  deadline: string
  scheduled_month: string
  status: string
  progress_percent: number
  is_overdue: boolean
}

interface Scope3Category {
  number: number
  name: string
  is_measured: boolean
  total_co2e: number
  percentage: number
}

interface EmissionSourceRecord {
  id: number
  source_name: string
  source_category: string
  scope: string
  activity_value: number
  activity_unit: string
  co2e_tonnes: number
  percentage: number
  data_quality: string
}

interface CertificationState {
  status: string
  readiness_percent: number
  evidence_checklist: Array<{
    description: string
    uploaded: boolean
    verified: boolean
  }>
  actions_completed: number
  actions_total: number
  data_quality_met: boolean
}

interface DataQualityState {
  overall_score: number
  max_score: number
  scopes: Record<string, { score: number; actual_pct: number; recommendations: string[] }>
  priority_improvements: Array<{ action: string; impact: string }>
}

// Bounded error state for deterministic UX
type LoadState = 'idle' | 'loading' | 'success' | 'error' | 'setup_required'

export default function PlanetMark() {
  const { t } = useTranslation()
  const now = new Date()
  const defaultYear = now.getUTCFullYear()
  const [activeTab, setActiveTab] = useState<
    'dashboard' | 'emissions' | 'actions' | 'quality' | 'scope3' | 'certification' | 'imported'
  >('dashboard')
  const [years, setYears] = useState<ReportingYear[]>([])
  const [currentYear, setCurrentYear] = useState<ReportingYear | null>(null)
  const [actions, setActions] = useState<ImprovementAction[]>([])
  const [scope3Categories, setScope3Categories] = useState<Scope3Category[]>([])
  const [emissionSources, setEmissionSources] = useState<EmissionSourceRecord[]>([])
  const [certification, setCertification] = useState<CertificationState | null>(null)
  const [dataQuality, setDataQuality] = useState<DataQualityState | null>(null)
  const [loadState, setLoadState] = useState<LoadState>('idle')
  const [errorClass, setErrorClass] = useState<ErrorClass | null>(null)
  const [setupRequired, setSetupRequired] = useState<SetupRequiredResponse | null>(null)
  const [importedRecords, setImportedRecords] = useState<ExternalAuditRecordSummary[]>([])
  const [importedTotal, setImportedTotal] = useState(0)
  const [loadingImported, setLoadingImported] = useState(false)
  const [isCreatingYear, setIsCreatingYear] = useState(false)
  const [setupActionError, setSetupActionError] = useState<string | null>(null)
  // New Planet Mark enhancement state
  const [actionItems, setActionItems] = useState<ActionItem[]>([])
  const [actionsSummary, setActionsSummary] = useState<{
    total: number; completed: number; in_progress: number; overdue: number
    not_started: number; completion_rate_percent: number; avg_progress_percent: number
  } | null>(null)
  const [selectedActionIds, setSelectedActionIds] = useState<Set<number>>(new Set())
  const [showImportModal, setShowImportModal] = useState(false)
  const [bulkStatus, setBulkStatus] = useState('')
  const [evidenceList, setEvidenceList] = useState<Array<{
    id: number; document_name: string; document_type: string; evidence_category: string
    period_covered: string | null; file_size_kb: number | null; mime_type: string | null
    is_verified: boolean; verified_by: string | null; linked_action_id: number | null
    notes: string | null; uploaded_by: string | null; uploaded_at: string; storage_key: string | null
  }>>([])
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

  const transformYear = (apiYear: {
    id: number
    year_label: string
    year_number: number
    period: string
    average_fte: number
    total_emissions: number
    emissions_per_fte: number
    scope_1: number
    scope_2_market: number
    scope_3: number
    data_quality: number
    certification_status: string
    is_baseline: boolean
  }): ReportingYear => ({
    id: apiYear.id,
    year_label: apiYear.year_label,
    year_number: apiYear.year_number,
    period: apiYear.period,
    total_emissions: apiYear.total_emissions,
    emissions_per_fte: apiYear.emissions_per_fte,
    fte: apiYear.average_fte,
    scope_1: apiYear.scope_1,
    scope_2: apiYear.scope_2_market,
    scope_3: apiYear.scope_3,
    data_quality: apiYear.data_quality,
    certification_status: apiYear.certification_status,
    is_baseline: apiYear.is_baseline,
  })

  const transformAction = (
    apiAction: {
      id: number
      action_id: string
      action_title: string
      owner: string
      deadline: string
      scheduled_month: string
      status: string
      progress_percent: number
      is_overdue: boolean
    },
  ): ImprovementAction => ({
    id: apiAction.id,
    action_id: apiAction.action_id,
    action_title: apiAction.action_title,
    owner: apiAction.owner || 'Unassigned',
    deadline: apiAction.deadline,
    scheduled_month: apiAction.scheduled_month,
    status: apiAction.status,
    progress_percent: apiAction.progress_percent,
    is_overdue: apiAction.is_overdue,
  })

  const transformScope3 = (apiScope3: {
    number: number
    name: string
    is_measured: boolean
    total_co2e: number
    percentage: number
  }): Scope3Category => ({
    number: apiScope3.number,
    name: apiScope3.name,
    is_measured: apiScope3.is_measured,
    total_co2e: apiScope3.total_co2e,
    percentage: apiScope3.percentage,
  })

  const loadYearDetails = useCallback(async (yearId: number) => {
    const [
      sourcesResponse,
      actionsResponse,
      scope3Response,
      certificationResponse,
      qualityResponse,
      summaryResponse,
      evidenceResponse,
    ] = await Promise.allSettled([
      planetMarkApi.listSources(yearId),
      planetMarkApi.listActions(yearId),
      planetMarkApi.getScope3(yearId),
      planetMarkApi.getCertification(yearId),
      planetMarkApi.getDataQuality(yearId),
      planetMarkApi.getActionsSummary(yearId),
      planetMarkApi.listEvidence(yearId),
    ])

    setEmissionSources(
      sourcesResponse.status === 'fulfilled' ? (sourcesResponse.value.data.sources ?? []) : [],
    )

    if (actionsResponse.status === 'fulfilled') {
      const rawActions = actionsResponse.value.data.actions ?? []
      setActions(rawActions.map(transformAction))
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      setActionItems(rawActions.map((a: any) => ({
        id: a.id as number,
        action_id: a.action_id as string,
        action_title: a.action_title as string,
        owner: (a.owner as string | null | undefined) || 'Unassigned',
        deadline: a.deadline as string,
        status: a.status as string,
        progress_percent: (a.progress_percent as number) ?? 0,
        target_scope: (a.target_scope as string | null | undefined) ?? undefined,
        expected_reduction_pct: (a.expected_reduction_pct as number | null | undefined) ?? 0,
        is_overdue: a.is_overdue as boolean,
        notes: (a.notes as string | null | undefined) ?? null,
      })))
    } else {
      setActions([])
      setActionItems([])
    }

    setScope3Categories(
      scope3Response.status === 'fulfilled'
        ? (scope3Response.value.data.categories ?? []).map(transformScope3)
        : [],
    )
    setCertification(
      certificationResponse.status === 'fulfilled'
        ? {
            status: certificationResponse.value.data.status,
            readiness_percent: certificationResponse.value.data.readiness_percent,
            evidence_checklist: certificationResponse.value.data.evidence_checklist,
            actions_completed: certificationResponse.value.data.actions_completed,
            actions_total: certificationResponse.value.data.actions_total,
            data_quality_met: certificationResponse.value.data.data_quality_met,
          }
        : null,
    )
    setDataQuality(
      qualityResponse.status === 'fulfilled'
        ? {
            overall_score: qualityResponse.value.data.overall_score,
            max_score: qualityResponse.value.data.max_score,
            scopes: qualityResponse.value.data.scopes,
            priority_improvements: qualityResponse.value.data.priority_improvements,
          }
        : null,
    )
    if (summaryResponse.status === 'fulfilled') {
      setActionsSummary(summaryResponse.value.data)
    }
    if (evidenceResponse.status === 'fulfilled') {
      setEvidenceList(evidenceResponse.value.data.evidence ?? [])
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
        const dashboard = dashboardResponse.data
        const yearsPayload = yearsResponse.data

        if (isSetupRequired(dashboard)) {
          setSetupRequired(dashboard)
          setLoadState('setup_required')
          // Pre-load imported records so setup screen can show "You have N imported reports"
          try {
            const importedRes = await externalAuditRecordsApi.list({ scheme: 'planet_mark' })
            setImportedRecords(importedRes.data.records)
            setImportedTotal(importedRes.data.total)
          } catch { /* non-fatal */ }
          return
        }
        if (isSetupRequired(yearsPayload)) {
          setSetupRequired(yearsPayload)
          setLoadState('setup_required')
          return
        }

        const transformedYears: ReportingYear[] = (yearsPayload.years ?? []).map(transformYear)
        transformedYears.sort((a, b) => b.year_number - a.year_number)

        setYears(transformedYears)
        setCurrentYear(transformedYears[0] || null)

        setLoadState('success')
      } catch (err) {
        const apiError = createApiError(err)
        setErrorClass(apiError.error_class)

        // Auto-retry once for transient network errors
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

  const handleCreateReportingYear = async (event: React.FormEvent) => {
    event.preventDefault()
    setSetupActionError(null)

    const averageFte = Number(setupYearForm.average_fte)
    const reductionTarget = Number(setupYearForm.reduction_target_percent)
    if (!setupYearForm.year_label.trim()) {
      setSetupActionError('Reporting year label is required.')
      return
    }
    if (!setupYearForm.period_start || !setupYearForm.period_end) {
      setSetupActionError('Please provide a reporting period start and end date.')
      return
    }
    if (setupYearForm.period_end < setupYearForm.period_start) {
      setSetupActionError('Reporting period end date must be on or after the start date.')
      return
    }
    if (!Number.isFinite(averageFte) || averageFte <= 0) {
      setSetupActionError('Average FTE must be greater than zero.')
      return
    }
    if (!Number.isFinite(reductionTarget) || reductionTarget < 0) {
      setSetupActionError('Reduction target percent must be zero or greater.')
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
      setSetupActionError(apiError.detail || 'Failed to create Planet Mark reporting year.')
    } finally {
      setIsCreatingYear(false)
    }
  }

  useEffect(() => {
    loadData()
  }, [loadData])

  useEffect(() => {
    if (!currentYear) return
    void loadYearDetails(currentYear.id)
  }, [currentYear, loadYearDetails])

  // Reset per-year data when year changes to avoid stale state on slow networks
  useEffect(() => {
    if (!currentYear) return
    setActionsSummary(null)
    setEvidenceList([])
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentYear?.id])

  const [importedError, setImportedError] = useState<string | null>(null)
  const [applyingImportId, setApplyingImportId] = useState<number | null>(null)
  const [appliedImportIds, setAppliedImportIds] = useState<Set<number>>(new Set())
  const [expandedPreviewIds, setExpandedPreviewIds] = useState<Set<number>>(new Set())

  useEffect(() => {
    if (activeTab !== 'imported') return
    let cancelled = false
    const loadImported = async () => {
      setLoadingImported(true)
      setImportedError(null)
      try {
        const res = await externalAuditRecordsApi.list({ scheme: 'planet_mark' })
        if (!cancelled) {
          setImportedRecords(res.data.records)
          setImportedTotal(res.data.total)
        }
      } catch (err) {
        if (!cancelled) {
          setImportedRecords([])
          setImportedError(createApiError(err).detail || 'Failed to load imported assessments.')
        }
      } finally {
        if (!cancelled) setLoadingImported(false)
      }
    }
    void loadImported()
    return () => { cancelled = true }
  }, [activeTab])

  const handleApplyImport = async (importJobId: number) => {
    setApplyingImportId(importJobId)
    try {
      const res = await planetMarkApi.applyImport(importJobId)
      const result = res.data
      if (result.status === 'no_carbon_data') {
        setImportedError(
          result.detail ||
          'No carbon data was extracted from this import. The report may need to be re-processed, or you can enter emission data manually in the Planet Mark section.'
        )
      } else {
        setAppliedImportIds((prev) => new Set([...prev, importJobId]))
        // Refresh all planet mark data so dashboard reflects the newly applied data
        await loadData()
        // Auto-switch to dashboard and select the synced year
        if (result.year_id) {
          const syncedYearId = result.year_id
          setYears((prev) => {
            const matched = prev.find((y) => y.id === syncedYearId)
            if (matched) setCurrentYear(matched)
            return prev
          })
          void loadYearDetails(syncedYearId)
        }
        setActiveTab('dashboard')
      }
    } catch (err) {
      const apiErr = createApiError(err)
      setImportedError(`Failed to apply import: ${apiErr.detail || 'Unknown error'}`)
    } finally {
      setApplyingImportId(null)
    }
  }

  const togglePreview = (recordId: number) => {
    setExpandedPreviewIds((prev) => {
      const next = new Set(prev)
      if (next.has(recordId)) next.delete(recordId)
      else next.add(recordId)
      return next
    })
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed':
        return 'bg-emerald-500/20 text-emerald-400'
      case 'in_progress':
        return 'bg-blue-500/20 text-blue-400'
      case 'planned':
        return 'bg-gray-500/20 text-gray-400'
      case 'delayed':
        return 'bg-red-500/20 text-red-400'
      case 'certified':
        return 'bg-emerald-500/20 text-emerald-400'
      default:
        return 'bg-gray-500/20 text-gray-400'
    }
  }

  const completedActions = actions.filter((a) => a.status === 'completed').length
  const yoyChange =
    currentYear && years.length >= 2
      ? ((currentYear.emissions_per_fte - years[1].emissions_per_fte) /
          years[1].emissions_per_fte) *
        100
      : null

  // Handle SETUP_REQUIRED state with dedicated panel
  if (loadState === 'setup_required' && setupRequired) {
    return (
      <div className="min-h-screen bg-background text-foreground p-6">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center md:justify-between mb-8">
          <div className="flex items-center gap-4">
            <div className="p-3 bg-primary/10 rounded-xl">
              <Leaf className="w-8 h-8 text-primary" />
            </div>
            <div>
              <h1 className="text-3xl font-bold text-foreground">{t('planet_mark.title')}</h1>
              <p className="text-muted-foreground">{t('planet_mark.subtitle')}</p>
            </div>
          </div>
        </div>

        {/* Setup Required Panel */}
        <SetupRequiredPanel
          response={setupRequired}
          onRetry={() => {
            loadData()
          }}
        />

        {/* Import-aware prompt: if the user has already uploaded a Planet Mark report */}
        {importedRecords.length > 0 && (
          <div className="mt-6 max-w-lg mx-auto rounded-xl border border-primary/30 bg-primary/5 p-4 flex items-start gap-3">
            <FileUp className="w-5 h-5 text-primary shrink-0 mt-0.5" />
            <div>
              <p className="text-sm font-medium text-foreground">
                You have {importedRecords.length} imported Planet Mark report{importedRecords.length > 1 ? 's' : ''}.
              </p>
              <p className="text-xs text-muted-foreground mt-1">
                After creating a reporting year below, go to the{' '}
                <strong>Imported Assessments</strong> tab and click{' '}
                <strong>Apply Carbon Data</strong> to populate it automatically.
              </p>
            </div>
          </div>
        )}

        {setupRequired.next_action.includes('/api/v1/planet-mark/years') ? (
          <div className="mt-8 max-w-lg mx-auto bg-card border border-border rounded-xl shadow-lg p-6">
            <div className="flex items-center justify-between gap-4 mb-4">
              <div>
                <h2 className="text-lg font-semibold text-foreground">Create Reporting Year</h2>
                <p className="text-sm text-muted-foreground">
                  Complete first-time Planet Mark setup without leaving the app.
                </p>
              </div>
              <Plus className="w-5 h-5 text-primary" />
            </div>
            <form className="space-y-4" onSubmit={handleCreateReportingYear}>
              <div className="grid gap-4 sm:grid-cols-2">
                <label className="space-y-2 text-sm text-foreground">
                  <span className="font-medium">Year Label</span>
                  <input
                    className="w-full rounded-lg border border-border bg-background px-3 py-2"
                    value={setupYearForm.year_label}
                    onChange={(e) => setSetupYearForm((prev) => ({ ...prev, year_label: e.target.value }))}
                  />
                </label>
                <label className="space-y-2 text-sm text-foreground">
                  <span className="font-medium">Year Number</span>
                  <input
                    type="number"
                    min="1"
                    className="w-full rounded-lg border border-border bg-background px-3 py-2"
                    value={setupYearForm.year_number}
                    onChange={(e) =>
                      setSetupYearForm((prev) => ({ ...prev, year_number: Number(e.target.value) || defaultYear }))
                    }
                  />
                </label>
                <label className="space-y-2 text-sm text-foreground">
                  <span className="font-medium">Period Start</span>
                  <input
                    type="date"
                    className="w-full rounded-lg border border-border bg-background px-3 py-2"
                    value={setupYearForm.period_start}
                    onChange={(e) => setSetupYearForm((prev) => ({ ...prev, period_start: e.target.value }))}
                  />
                </label>
                <label className="space-y-2 text-sm text-foreground">
                  <span className="font-medium">Period End</span>
                  <input
                    type="date"
                    className="w-full rounded-lg border border-border bg-background px-3 py-2"
                    value={setupYearForm.period_end}
                    onChange={(e) => setSetupYearForm((prev) => ({ ...prev, period_end: e.target.value }))}
                  />
                </label>
                <label className="space-y-2 text-sm text-foreground">
                  <span className="font-medium">Average FTE</span>
                  <input
                    type="number"
                    min="1"
                    step="0.1"
                    className="w-full rounded-lg border border-border bg-background px-3 py-2"
                    value={setupYearForm.average_fte}
                    onChange={(e) => setSetupYearForm((prev) => ({ ...prev, average_fte: e.target.value }))}
                  />
                </label>
                <label className="space-y-2 text-sm text-foreground">
                  <span className="font-medium">Reduction Target %</span>
                  <input
                    type="number"
                    min="0"
                    step="0.1"
                    className="w-full rounded-lg border border-border bg-background px-3 py-2"
                    value={setupYearForm.reduction_target_percent}
                    onChange={(e) =>
                      setSetupYearForm((prev) => ({ ...prev, reduction_target_percent: e.target.value }))
                    }
                  />
                </label>
              </div>
              <label className="space-y-2 text-sm text-foreground block">
                <span className="font-medium">Organization Name</span>
                <input
                  className="w-full rounded-lg border border-border bg-background px-3 py-2"
                  value={setupYearForm.organization_name}
                  onChange={(e) => setSetupYearForm((prev) => ({ ...prev, organization_name: e.target.value }))}
                />
              </label>
              <label className="flex items-center gap-2 text-sm text-foreground">
                <input
                  type="checkbox"
                  checked={setupYearForm.is_baseline_year}
                  onChange={(e) =>
                    setSetupYearForm((prev) => ({ ...prev, is_baseline_year: e.target.checked }))
                  }
                />
                <span>Set as baseline reporting year</span>
              </label>
              {setupActionError ? (
                <div className="rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                  {setupActionError}
                </div>
              ) : null}
              <button
                type="submit"
                disabled={isCreatingYear}
                className="w-full rounded-lg bg-primary px-4 py-2 font-medium text-primary-foreground hover:bg-primary-hover disabled:opacity-60"
              >
                {isCreatingYear ? 'Creating reporting year...' : 'Create Reporting Year'}
              </button>
            </form>
          </div>
        ) : null}
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-background text-foreground p-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between mb-8">
        <div className="flex items-center gap-4">
          <div className="p-3 bg-primary/10 rounded-xl">
            <Leaf className="w-8 h-8 text-primary" />
          </div>
          <div>
            <h1 className="text-3xl font-bold text-foreground">Planet Mark Carbon</h1>
            <p className="text-muted-foreground">Net-Zero Journey • GHG Protocol Aligned</p>
          </div>
        </div>
        <div className="flex gap-3 mt-4 md:mt-0">
          <button
            onClick={() => {
              if (currentYear) {
                window.open(`/api/v1/planet-mark/years/${currentYear.id}/export`, '_blank')
              }
            }}
            disabled={!currentYear}
            className="flex items-center gap-2 px-4 py-2 bg-secondary border border-border hover:bg-surface rounded-lg transition-colors disabled:opacity-40"
            aria-label="Export carbon report"
          >
            <Download className="w-4 h-4" />
            {t('planet_mark.export_report')}
          </button>
          <button
            onClick={() => setActiveTab('emissions')}
            className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground hover:bg-primary-hover rounded-lg transition-colors"
          >
            <Plus className="w-4 h-4" />
            {t('planet_mark.add_emission')}
          </button>
        </div>
      </div>

      {/* Year Selector & Summary Banner */}
      {currentYear && (
        <div className="bg-gradient-to-r from-primary to-primary-hover rounded-xl p-6 mb-8">
          <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-6">
            <div>
              <div className="flex items-center gap-3 mb-2">
                <select
                  value={currentYear.id}
                  onChange={(e) =>
                    setCurrentYear(years.find((y) => y.id === parseInt(e.target.value)) || years[0])
                  }
                  className="bg-primary-foreground/20 border border-primary-foreground/30 rounded-lg px-3 py-1 text-primary-foreground font-bold text-lg"
                >
                  {years.map((y) => (
                    <option key={y.id} value={y.id} className="bg-card text-foreground">
                      {y.year_label} {y.is_baseline ? `(${t('planet_mark.baseline')})` : ''}
                    </option>
                  ))}
                </select>
                {currentYear.certification_status === 'certified' && (
                  <span className="px-3 py-1 bg-primary-foreground/20 rounded-full text-sm font-medium flex items-center gap-1 text-primary-foreground">
                    <Award className="w-4 h-4" /> {t('planet_mark.certified')}
                  </span>
                )}
              </div>
              <p className="text-primary-foreground/80">Reporting: {currentYear.period}</p>
            </div>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
              <div className="text-center">
                <div className="text-3xl font-bold text-primary-foreground">
                  {(currentYear.total_emissions ?? 0).toFixed(1)}
                </div>
                <div className="text-primary-foreground/80 text-sm">
                  {t('planet_mark.tco2e_total')}
                </div>
              </div>
              <div className="text-center">
                <div className="text-3xl font-bold text-primary-foreground">
                  {(currentYear.emissions_per_fte ?? 0).toFixed(2)}
                </div>
                <div className="text-primary-foreground/80 text-sm">
                  {t('planet_mark.tco2e_fte')}
                </div>
              </div>
              <div className="text-center">
                <div
                  className={`text-3xl font-bold ${yoyChange && yoyChange < 0 ? 'text-primary-foreground' : 'text-warning'}`}
                >
                  {yoyChange !== null && yoyChange !== undefined ? `${yoyChange > 0 ? '+' : ''}${yoyChange.toFixed(1)}%` : '—'}
                </div>
                <div className="text-primary-foreground/80 text-sm">
                  {t('planet_mark.vs_baseline')}
                </div>
              </div>
              <div className="text-center">
                <div className="text-3xl font-bold text-primary-foreground">
                  {currentYear.data_quality}/16
                </div>
                <div className="text-primary-foreground/80 text-sm">
                  {t('planet_mark.data_quality')}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Tabs */}
      <div
        role="tablist"
        aria-label="Planet Mark sections"
        className="flex gap-2 mb-6 border-b border-border pb-2 overflow-x-auto"
      >
        {[
          { id: 'dashboard', label: t('planet_mark.dashboard'), icon: BarChart3 },
          { id: 'emissions', label: t('planet_mark.emissions'), icon: Factory },
          { id: 'scope3', label: t('planet_mark.scope3_categories'), icon: Globe },
          { id: 'actions', label: t('planet_mark.improvement_plan'), icon: Target },
          { id: 'quality', label: t('planet_mark.data_quality'), icon: Gauge },
          { id: 'certification', label: t('planet_mark.certification'), icon: Award },
          { id: 'imported', label: t('planet_mark.imported_assessments'), icon: ClipboardCheck },
        ].map((tab, idx, arr) => {
          const Icon = tab.icon
          const isActive = activeTab === tab.id
          return (
            <button
              key={tab.id}
              role="tab"
              aria-selected={isActive}
              tabIndex={isActive ? 0 : -1}
              onClick={() => setActiveTab(tab.id as typeof activeTab)}
              onKeyDown={(e) => {
                if (e.key === 'ArrowRight') {
                  const next = arr[(idx + 1) % arr.length]
                  setActiveTab(next.id as typeof activeTab)
                } else if (e.key === 'ArrowLeft') {
                  const prev = arr[(idx - 1 + arr.length) % arr.length]
                  setActiveTab(prev.id as typeof activeTab)
                }
              }}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-colors whitespace-nowrap ${
                isActive
                  ? 'bg-primary text-primary-foreground'
                  : 'text-muted-foreground hover:bg-surface hover:text-foreground'
              }`}
            >
              <Icon className="w-4 h-4" />
              {tab.label}
            </button>
          )
        })}
      </div>

      {/* Loading State */}
      {loadState === 'loading' && (
        <div className="flex flex-col items-center justify-center py-12">
          <RefreshCw className="w-8 h-8 text-primary animate-spin mb-4" />
          <p className="text-muted-foreground">{t('planet_mark.loading')}</p>
        </div>
      )}

      {/* Error State */}
      {loadState === 'error' && (
        <div className="flex flex-col items-center justify-center py-12 bg-card rounded-xl border border-border">
          <XCircle className="w-12 h-12 text-destructive mb-4" />
          <h3 className="text-lg font-semibold text-foreground mb-2">
            {t('planet_mark.failed_to_load')}
          </h3>
          <p className="text-muted-foreground mb-4">
            {errorClass === ErrorClass.NETWORK_ERROR && t('planet_mark.error_network')}
            {errorClass === ErrorClass.SERVER_ERROR && t('planet_mark.error_server')}
            {errorClass === ErrorClass.AUTH_ERROR && t('planet_mark.error_auth')}
            {errorClass === ErrorClass.NOT_FOUND && t('planet_mark.error_not_found')}
            {(errorClass === ErrorClass.UNKNOWN || !errorClass) && t('planet_mark.error_unknown')}
          </p>
          <button
            onClick={() => {
              loadData()
            }}
            className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground hover:bg-primary-hover rounded-lg transition-colors"
          >
            <RefreshCw className="w-4 h-4" />
            {t('planet_mark.try_again')}
          </button>
        </div>
      )}

      {/* Empty State */}
      {loadState === 'success' && years.length === 0 && (
        <div className="flex flex-col items-center justify-center py-12 bg-card rounded-xl border border-border">
          <Leaf className="w-12 h-12 text-muted-foreground mb-4" />
          <h3 className="text-lg font-semibold text-foreground mb-2">{t('planet_mark.no_data')}</h3>
          <p className="text-muted-foreground mb-4">{t('planet_mark.no_data_description')}</p>
          <button
            onClick={() => loadData()}
            className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground hover:bg-primary-hover rounded-lg transition-colors"
          >
            <Plus className="w-4 h-4" />
            {t('planet_mark.add_reporting_year')}
          </button>
        </div>
      )}

      {loadState === 'success' && years.length > 0 && (
        <>
          {/* Dashboard Tab */}
          {activeTab === 'dashboard' && currentYear && (
            <div className="space-y-6">
              {/* Scope Breakdown */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                {[
                  {
                    scopeKey: 'planet_mark.scope1',
                    value: currentYear.scope_1,
                    color: 'bg-orange-500',
                    icon: Fuel,
                    labelKey: 'planet_mark.scope1_label',
                    detailKey: 'planet_mark.scope1_sources',
                  },
                  {
                    scopeKey: 'planet_mark.scope2',
                    value: currentYear.scope_2,
                    color: 'bg-blue-500',
                    icon: Zap,
                    labelKey: 'planet_mark.scope2_label',
                    detailKey: 'planet_mark.scope2_sources',
                  },
                  {
                    scopeKey: 'planet_mark.scope3',
                    value: currentYear.scope_3,
                    color: 'bg-purple-500',
                    icon: Globe,
                    labelKey: 'planet_mark.scope3_label',
                    detailKey: 'planet_mark.scope3_sources',
                  },
                ].map((scope) => {
                  const Icon = scope.icon
                  const pct = (
                    currentYear.total_emissions
                      ? (scope.value / currentYear.total_emissions) * 100
                      : 0
                  ).toFixed(1)
                  return (
                    <div
                      key={scope.scopeKey}
                      className="bg-card rounded-xl p-6 border border-border"
                    >
                      <div className="flex items-center justify-between mb-4">
                        <div className="flex items-center gap-3">
                          <div className={`p-3 ${scope.color} rounded-xl`}>
                            <Icon className="w-6 h-6 text-white" />
                          </div>
                          <div>
                            <div className="font-bold text-foreground">{t(scope.scopeKey)}</div>
                            <div className="text-xs text-muted-foreground">{t(scope.labelKey)}</div>
                          </div>
                        </div>
                        <div className="text-right">
                          <div className="text-2xl font-bold text-foreground">
                            {scope.value.toFixed(1)}
                          </div>
                          <div className="text-xs text-muted-foreground">tCO₂e</div>
                        </div>
                      </div>
                      <div className="w-full bg-surface rounded-full h-3 mb-2">
                        <div
                          className={`h-3 rounded-full ${scope.color}`}
                          style={{ width: `${pct}%` }}
                        ></div>
                      </div>
                      <div className="flex justify-between text-sm">
                        <span className="text-muted-foreground">{t(scope.detailKey)}</span>
                        <span className="text-foreground font-medium">{pct}%</span>
                      </div>
                    </div>
                  )
                })}
              </div>

              {/* Key Sources & Action Progress */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Key Emission Sources */}
                <div className="bg-card rounded-xl border border-border">
                  <div className="p-4 bg-surface border-b border-border">
                    <h3 className="font-bold text-foreground">
                      {t('planet_mark.key_emission_sources')}
                    </h3>
                    <p className="text-sm text-muted-foreground">
                      {t('planet_mark.key_emission_sources_desc')}
                    </p>
                  </div>
                  <div className="p-4 space-y-4">
                    {emissionSources.length === 0 && (
                      <p className="text-sm text-muted-foreground">
                        No live emission sources have been recorded for this reporting year yet.
                      </p>
                    )}
                    {emissionSources.slice(0, 5).map((source) => {
                      const iconByScope: Record<string, React.ElementType> = {
                        scope_1: Truck,
                        scope_2: Zap,
                        scope_3: Globe,
                      }
                      const Icon = iconByScope[source.scope] || Building2
                      return (
                        <div key={source.id} className="flex items-center gap-4">
                          <Icon className="w-5 h-5 text-primary" />
                          <div className="flex-grow">
                            <div className="flex justify-between text-sm mb-1">
                              <span className="text-foreground">{source.source_name}</span>
                              <span className="text-muted-foreground">
                                {source.co2e_tonnes.toFixed(1)} tCO₂e ({source.percentage.toFixed(1)}%)
                              </span>
                            </div>
                            <div className="w-full bg-surface rounded-full h-2">
                              <div
                                className="h-2 rounded-full bg-primary"
                                style={{ width: `${Math.min(source.percentage, 100)}%` }}
                              ></div>
                            </div>
                          </div>
                        </div>
                      )
                    })}
                  </div>
                </div>

                {/* Improvement Plan Progress */}
                <div className="bg-slate-800 rounded-xl border border-slate-700">
                  <div className="p-4 bg-slate-700 border-b border-slate-600 flex justify-between items-center">
                    <div>
                      <h3 className="font-bold text-white">{t('planet_mark.improvement_plan')}</h3>
                      <p className="text-sm text-gray-400">
                        {t('planet_mark.actions_completed', {
                          completed: completedActions,
                          total: actions.length,
                        })}
                      </p>
                    </div>
                    <div className="text-right">
                      <div className="text-2xl font-bold text-green-400">
                        {actions.length > 0
                          ? Math.round((completedActions / actions.length) * 100)
                          : 0}
                        %
                      </div>
                      <div className="text-xs text-gray-400">{t('planet_mark.complete')}</div>
                    </div>
                  </div>
                  <div className="p-4 space-y-3 max-h-80 overflow-y-auto">
                    {actions.slice(0, 6).map((action) => (
                      <div
                        key={action.id}
                        className="flex items-center gap-3 p-2 bg-slate-700/50 rounded-lg"
                      >
                        {action.status === 'completed' ? (
                          <CheckCircle2 className="w-5 h-5 text-green-400 flex-shrink-0" />
                        ) : action.status === 'in_progress' ? (
                          <Clock className="w-5 h-5 text-blue-400 flex-shrink-0" />
                        ) : (
                          <div className="w-5 h-5 border-2 border-gray-500 rounded-full flex-shrink-0" />
                        )}
                        <div className="flex-grow min-w-0">
                          <div className="text-sm text-white truncate">{action.action_title}</div>
                          <div className="text-xs text-gray-400">
                            {action.scheduled_month} • {action.owner}
                          </div>
                        </div>
                        <span
                          className={`px-2 py-0.5 rounded text-xs ${getStatusColor(action.status)}`}
                        >
                          {action.progress_percent}%
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {certification && (
                <div className="bg-card rounded-xl border border-border">
                  <div className="p-4 bg-surface border-b border-border">
                    <h3 className="font-bold text-foreground">{t('planet_mark.certification')}</h3>
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4 p-4">
                    <div className="rounded-lg border border-border p-4">
                      <div className="text-sm text-muted-foreground">{t('planet_mark.certification_status')}</div>
                      <div className="mt-1 text-lg font-semibold text-foreground">{certification.status}</div>
                    </div>
                    <div className="rounded-lg border border-border p-4">
                      <div className="text-sm text-muted-foreground">{t('planet_mark.complete')}</div>
                      <div className="mt-1 text-lg font-semibold text-foreground">
                        {certification.actions_total > 0
                          ? `${certification.actions_completed}/${certification.actions_total}`
                          : '0/0'}
                      </div>
                    </div>
                    <div className="rounded-lg border border-border p-4">
                      <div className="text-sm text-muted-foreground">{t('planet_mark.evidence_checklist')}</div>
                      <div className="mt-1 text-lg font-semibold text-foreground">
                        {certification.readiness_percent}%
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Emissions Tab */}
          {activeTab === 'emissions' && currentYear && (
            <div className="space-y-6">
              <div className="bg-slate-800 rounded-xl border border-slate-700">
                <div className="p-4 bg-slate-700 border-b border-slate-600 flex justify-between items-center">
                  <h3 className="font-bold text-white">
                    {t('planet_mark.emission_sources_by_scope')}
                  </h3>
                  <button className="px-4 py-2 bg-green-600 hover:bg-green-700 rounded-lg text-sm font-medium transition-colors flex items-center gap-2">
                    <Plus className="w-4 h-4" /> {t('planet_mark.add_source')}
                  </button>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead className="bg-slate-700/50">
                      <tr>
                        <th className="px-4 py-3 text-left text-xs font-semibold text-gray-300 uppercase">
                          {t('planet_mark.source')}
                        </th>
                        <th className="px-4 py-3 text-left text-xs font-semibold text-gray-300 uppercase">
                          {t('planet_mark.scope')}
                        </th>
                        <th className="px-4 py-3 text-right text-xs font-semibold text-gray-300 uppercase">
                          {t('planet_mark.activity')}
                        </th>
                        <th className="px-4 py-3 text-right text-xs font-semibold text-gray-300 uppercase">
                          tCO₂e
                        </th>
                        <th className="px-4 py-3 text-center text-xs font-semibold text-gray-300 uppercase">
                          {t('planet_mark.pct_of_total')}
                        </th>
                        <th className="px-4 py-3 text-center text-xs font-semibold text-gray-300 uppercase">
                          {t('planet_mark.data_quality')}
                        </th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-700">
                      {emissionSources.map((row) => (
                        <tr key={row.id} className="hover:bg-slate-700/50">
                          <td className="px-4 py-3 font-medium text-white">{row.source_name}</td>
                          <td className="px-4 py-3">
                            <span
                              className={`px-2 py-1 rounded text-xs ${
                                row.scope === 'scope_1'
                                  ? 'bg-orange-500/20 text-orange-400'
                                  : row.scope === 'scope_2'
                                    ? 'bg-blue-500/20 text-blue-400'
                                    : 'bg-purple-500/20 text-purple-400'
                              }`}
                            >
                              {row.scope.replace('_', ' ').replace('scope', 'Scope')}
                            </span>
                          </td>
                          <td className="px-4 py-3 text-right text-gray-300">
                            {row.activity_value} {row.activity_unit}
                          </td>
                          <td className="px-4 py-3 text-right font-bold text-white">
                            {row.co2e_tonnes.toFixed(1)}
                          </td>
                          <td className="px-4 py-3 text-center text-gray-400">
                            {row.percentage.toFixed(1)}%
                          </td>
                          <td className="px-4 py-3 text-center">
                            <span
                              className={`px-2 py-1 rounded text-xs ${
                                row.data_quality === 'actual'
                                  ? 'bg-green-500/20 text-green-400'
                                  : row.data_quality === 'calculated'
                                    ? 'bg-yellow-500/20 text-yellow-400'
                                    : 'bg-gray-500/20 text-gray-400'
                              }`}
                            >
                              {row.data_quality}
                            </span>
                          </td>
                        </tr>
                      ))}
                      {emissionSources.length === 0 && (
                        <tr>
                          <td colSpan={6} className="px-4 py-6 text-center text-gray-400">
                            No emission source records have been captured for this year yet.
                          </td>
                        </tr>
                      )}
                    </tbody>
                    <tfoot className="bg-slate-700/30">
                      <tr>
                        <td colSpan={3} className="px-4 py-3 font-bold text-white">
                          {t('planet_mark.total')}
                        </td>
                        <td className="px-4 py-3 text-right font-bold text-green-400">
                          {(currentYear.total_emissions ?? 0).toFixed(1)}
                        </td>
                        <td className="px-4 py-3 text-center font-bold text-white">100%</td>
                        <td></td>
                      </tr>
                    </tfoot>
                  </table>
                </div>
              </div>
            </div>
          )}

          {/* Scope 3 Categories Tab */}
          {activeTab === 'scope3' && (
            <div className="space-y-6">
              <div className="bg-slate-800 rounded-xl border border-slate-700">
                <div className="p-4 bg-slate-700 border-b border-slate-600">
                  <h3 className="font-bold text-white">{t('planet_mark.scope3_categories')}</h3>
                  <p className="text-sm text-gray-400">
                    {t('planet_mark.scope3_measured', {
                      count: scope3Categories.filter((c) => c.is_measured).length,
                    })}
                  </p>
                </div>
                <div className="p-4 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {scope3Categories.map((cat) => {
                    const icons: Record<number, React.ElementType> = {
                      1: ShoppingCart,
                      2: Building2,
                      3: Fuel,
                      4: Truck,
                      5: Trash2,
                      6: Briefcase,
                      7: Home,
                      8: Building2,
                      9: Truck,
                      10: Factory,
                      11: Users,
                      12: Trash2,
                      13: Building2,
                      14: Users,
                      15: BarChart3,
                    }
                    const Icon = icons[cat.number] || Globe
                    return (
                      <div
                        key={cat.number}
                        className={`p-4 rounded-lg border ${
                          cat.is_measured
                            ? 'bg-green-500/10 border-green-500/30'
                            : 'bg-slate-700/50 border-slate-600'
                        }`}
                      >
                        <div className="flex items-start justify-between mb-2">
                          <div className="flex items-center gap-2">
                            <div
                              className={`p-2 rounded-lg ${cat.is_measured ? 'bg-green-500/20' : 'bg-slate-600'}`}
                            >
                              <Icon
                                className={`w-4 h-4 ${cat.is_measured ? 'text-green-400' : 'text-gray-400'}`}
                              />
                            </div>
                            <span className="text-xs text-gray-400">Cat {cat.number}</span>
                          </div>
                          {cat.is_measured ? (
                            <CheckCircle2 className="w-5 h-5 text-green-400" />
                          ) : (
                            <div className="w-5 h-5 border border-gray-500 rounded-full" />
                          )}
                        </div>
                        <div className="text-sm font-medium text-white mb-1">{cat.name}</div>
                        {cat.is_measured && (
                          <div className="text-lg font-bold text-green-400">
                            {cat.total_co2e.toFixed(1)} tCO₂e
                          </div>
                        )}
                        {!cat.is_measured && (
                          <div className="text-sm text-gray-400">
                            {t('planet_mark.not_measured')}
                          </div>
                        )}
                      </div>
                    )
                  })}
                </div>
              </div>
            </div>
          )}

          {/* Actions Tab */}
          {activeTab === 'actions' && (
            <div className="space-y-4">
              {/* KPI strip */}
              {actionsSummary && <ActionSummaryKPIs summary={actionsSummary} />}

              {/* Toolbar */}
              <div className="flex items-center justify-between gap-3 flex-wrap">
                <h3 className="font-bold text-foreground text-lg">
                  {t('planet_mark.improvement_actions')}
                </h3>
                <div className="flex items-center gap-2">
                  {selectedActionIds.size > 0 && (
                    <div className="flex items-center gap-2">
                      <select
                        value={bulkStatus}
                        onChange={(e) => setBulkStatus(e.target.value)}
                        className="text-sm border border-gray-300 rounded-lg px-2 py-1.5 focus:ring-1 focus:ring-green-500 outline-none"
                        aria-label="Bulk status"
                      >
                        <option value="">Set status…</option>
                        <option value="in_progress">In Progress</option>
                        <option value="completed">Completed</option>
                        <option value="on_hold">On Hold</option>
                        <option value="cancelled">Cancelled</option>
                      </select>
                      <button
                        disabled={!bulkStatus || !currentYear}
                        onClick={async () => {
                          if (!currentYear || !bulkStatus) return
                          try {
                            await planetMarkApi.bulkUpdateActions(
                              currentYear.id,
                              Array.from(selectedActionIds),
                              bulkStatus,
                            )
                            setSelectedActionIds(new Set())
                            setBulkStatus('')
                            await loadYearDetails(currentYear.id)
                          } catch (err: unknown) {
                            const msg = err instanceof Error ? err.message : 'Bulk update failed'
                            alert(msg)
                          }
                        }}
                        className="px-3 py-1.5 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 disabled:opacity-40 transition-colors"
                      >
                        Apply ({selectedActionIds.size})
                      </button>
                    </div>
                  )}
                  <button
                    onClick={() => setShowImportModal(true)}
                    className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium transition-colors flex items-center gap-2"
                  >
                    <FileUp className="w-4 h-4" />
                    Import Plan
                  </button>
                  <button
                    onClick={() => setShowImportModal(true)}
                    className="px-4 py-2 bg-green-600 hover:bg-green-700 text-white rounded-lg text-sm font-medium transition-colors flex items-center gap-2"
                  >
                    <Plus className="w-4 h-4" /> {t('planet_mark.add_action')}
                  </button>
                </div>
              </div>

              {/* Action cards */}
              {actionItems.length === 0 ? (
                <div className="rounded-xl border border-dashed border-gray-300 p-10 text-center text-gray-500">
                  <Target className="w-10 h-10 mx-auto mb-2 opacity-30" />
                  <p className="font-medium">No improvement actions yet</p>
                  <p className="text-sm mt-1">Import your action plan or create actions manually.</p>
                </div>
              ) : (
                <div className="space-y-2">
                  {actionItems.map((action) => (
                    <ActionCard
                      key={action.id}
                      yearId={currentYear?.id ?? 0}
                      action={action}
                      selected={selectedActionIds.has(action.id)}
                      onSelect={(id, checked) => {
                        setSelectedActionIds((prev) => {
                          const next = new Set(prev)
                          if (checked) next.add(id)
                          else next.delete(id)
                          return next
                        })
                      }}
                      onUpdated={() => currentYear && loadYearDetails(currentYear.id)}
                    />
                  ))}
                </div>
              )}

              {/* Import modal */}
              {showImportModal && currentYear && (
                <ActionImportModal
                  yearId={currentYear.id}
                  onClose={() => setShowImportModal(false)}
                  onImported={async (_count) => {
                    setShowImportModal(false)
                    await loadYearDetails(currentYear.id)
                  }}
                />
              )}
            </div>
          )}

          {/* Data Quality Tab */}
          {activeTab === 'quality' && (
            <div className="space-y-6">
              {dataQuality ? (
                <>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                    {[
                      {
                        scopeKey: 'planet_mark.dq_scope_1_2',
                        score:
                          (dataQuality.scopes.scope_1?.score ?? 0) +
                          (dataQuality.scopes.scope_2?.score ?? 0),
                      },
                      {
                        scopeKey: 'planet_mark.dq_scope_3',
                        score: dataQuality.scopes.scope_3?.score ?? 0,
                      },
                      {
                        scopeKey: 'planet_mark.dq_scope_overall',
                        score: dataQuality.overall_score,
                      },
                    ].map((dq) => (
                      <div
                        key={dq.scopeKey}
                        className="bg-card rounded-xl p-6 border border-border"
                      >
                        <h3 className="font-bold text-foreground mb-4">{t(dq.scopeKey)}</h3>
                        <div className="relative w-32 h-32 mx-auto mb-4">
                          <svg className="w-full h-full transform -rotate-90">
                            <circle
                              cx="64"
                              cy="64"
                              r="56"
                              stroke="currentColor"
                              strokeWidth="8"
                              fill="transparent"
                              className="text-border"
                            />
                            <circle
                              cx="64"
                              cy="64"
                              r="56"
                              stroke="currentColor"
                              strokeWidth="8"
                              fill="transparent"
                              strokeDasharray={`${(dq.score / dataQuality.max_score) * 352} 352`}
                              className={dq.score >= 12 ? 'text-success' : 'text-warning'}
                            />
                          </svg>
                          <div className="absolute inset-0 flex flex-col items-center justify-center">
                            <span className="text-3xl font-bold text-foreground">{dq.score}</span>
                            <span className="text-sm text-muted-foreground">/ {dataQuality.max_score}</span>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>

                  <div className="bg-card rounded-xl border border-border">
                    <div className="p-4 bg-surface border-b border-border">
                      <h3 className="font-bold text-foreground">
                        {t('planet_mark.data_quality_recommendations')}
                      </h3>
                    </div>
                    <div className="p-4 space-y-4">
                      {dataQuality.priority_improvements.map((rec) => (
                        <div
                          key={`${rec.action}-${rec.impact}`}
                          className="flex items-center justify-between p-3 bg-surface/50 rounded-lg border border-border/50"
                        >
                          <span className="text-foreground">{rec.action}</span>
                          <span className="text-success font-medium">{rec.impact}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </>
              ) : (
                <div className="rounded-xl border border-border bg-card p-6 text-muted-foreground">
                  Live data quality metrics are not available for this reporting year yet.
                </div>
              )}
            </div>
          )}

          {/* Imported Assessments Tab */}
          {activeTab === 'imported' && (
            <div className="space-y-6">
              {/* Informational banner */}
              <div className="flex items-start gap-3 rounded-xl border border-primary/20 bg-primary/5 px-4 py-3 text-sm">
                <FileUp className="w-4 h-4 mt-0.5 shrink-0 text-primary" />
                <div className="text-muted-foreground space-y-1">
                  <p>
                    <span className="font-medium text-foreground">Planet Mark certification reports imported via the Audit pipeline appear here.</span>
                    {' '}Click <span className="font-medium text-primary">Apply to Dashboard</span> to populate your emissions data, improvement actions, Scope 3 breakdown, data quality scores and certification status.
                  </p>
                  <p className="text-xs">
                    Records already applied show a green badge. You can re-sync at any time to pick up any updated extraction.
                  </p>
                </div>
              </div>

              <div className="bg-card rounded-xl border border-border">
                <div className="p-4 bg-surface border-b border-border">
                  <h3 className="font-bold text-foreground flex items-center gap-2">
                    <ClipboardCheck className="w-5 h-5 text-primary" />
                    {t('planet_mark.imported_assessments_title')} ({importedTotal})
                  </h3>
                  <p className="text-sm text-muted-foreground">
                    {t('planet_mark.imported_assessments_desc')}
                  </p>
                </div>
                <div className="p-4">
                  {importedError && (
                    <div className="mb-4 rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive flex items-start gap-2">
                      <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />
                      <span className="flex-1">{importedError}</span>
                      <button
                        onClick={() => setImportedError(null)}
                        className="shrink-0 text-destructive/70 hover:text-destructive transition-colors"
                        aria-label="Dismiss"
                      >
                        <XCircle className="w-4 h-4" />
                      </button>
                    </div>
                  )}
                  {loadingImported && (
                    <div className="flex items-center gap-2 text-sm text-muted-foreground py-4">
                      <RefreshCw className="w-4 h-4 animate-spin" /> {t('planet_mark.loading_imported')}
                    </div>
                  )}
                  {!loadingImported && !importedError && importedRecords.length === 0 && (
                    <div className="text-center py-12">
                      <ClipboardCheck className="w-12 h-12 mx-auto text-muted-foreground mb-4" />
                      <h4 className="text-lg font-semibold text-muted-foreground mb-2">
                        {t('planet_mark.no_imported_assessments')}
                      </h4>
                      <p className="text-sm text-muted-foreground">
                        {t('planet_mark.no_imported_assessments_hint')}
                      </p>
                    </div>
                  )}
                  <div className="space-y-3">
                    {importedRecords.map((record) => {
                      const isApplied = appliedImportIds.has(record.import_job_id ?? -1)
                      const isApplying = applyingImportId === (record.import_job_id ?? -1)
                      const alreadyLinked = Boolean(record.carbon_reporting_year_id)
                      const carbonApplied = isApplied || alreadyLinked
                      const hasExtractedCarbon = record.scope_1_co2e != null || record.scope_2_co2e != null || record.scope_3_co2e != null
                      const isPreviewOpen = expandedPreviewIds.has(record.id)

                      return (
                        <div
                          key={record.id}
                          className={`rounded-lg border transition-all ${
                            carbonApplied
                              ? 'bg-success/5 border-success/30'
                              : 'bg-surface/50 border-border hover:border-primary/40'
                          }`}
                        >
                          <div className="p-4">
                            <div className="flex items-start justify-between mb-2">
                              <div className="flex-1 min-w-0">
                                <h4 className="font-medium text-foreground flex items-center gap-2 flex-wrap">
                                  {record.scheme_label || 'Planet Mark Assessment'}
                                  {carbonApplied && (
                                    <span className="inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full bg-success/15 text-success font-normal">
                                      <CheckCircle2 className="w-3 h-3" /> Applied to dashboard
                                    </span>
                                  )}
                                </h4>
                                <p className="text-sm text-muted-foreground">
                                  {record.issuer_name && `${record.issuer_name} · `}
                                  {record.report_date
                                    ? new Date(record.report_date).toLocaleDateString('en-GB', { year: 'numeric', month: 'short', day: 'numeric' })
                                    : 'Date not available'}
                                </p>
                                {hasExtractedCarbon && (
                                  <div className="flex items-center gap-3 mt-1.5 text-xs font-medium">
                                    {record.scope_1_co2e != null && (
                                      <span className="px-1.5 py-0.5 rounded bg-blue-500/10 text-blue-400">
                                        S1: {record.scope_1_co2e.toFixed(1)} tCO₂e
                                      </span>
                                    )}
                                    {record.scope_2_co2e != null && (
                                      <span className="px-1.5 py-0.5 rounded bg-purple-500/10 text-purple-400">
                                        S2: {record.scope_2_co2e.toFixed(1)} tCO₂e
                                      </span>
                                    )}
                                    {record.scope_3_co2e != null && (
                                      <span className="px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-400">
                                        S3: {record.scope_3_co2e.toFixed(1)} tCO₂e
                                      </span>
                                    )}
                                    <button
                                      onClick={() => togglePreview(record.id)}
                                      className="text-xs text-muted-foreground hover:text-primary underline-offset-2 hover:underline ml-1"
                                    >
                                      {isPreviewOpen ? 'Hide details' : 'Show details'}
                                    </button>
                                  </div>
                                )}
                              </div>
                              <div className="flex flex-col items-end gap-2 shrink-0 ml-4">
                                {record.score_percentage != null && (
                                  <span className="text-lg font-bold text-primary">
                                    {Math.round(record.score_percentage)}%
                                  </span>
                                )}
                                <div className={`text-xs px-2 py-0.5 rounded-full inline-block ${
                                  record.outcome_status === 'pass' || record.outcome_status === 'certified'
                                    ? 'bg-success/20 text-success'
                                    : record.outcome_status === 'fail' || record.outcome_status === 'not_certified'
                                      ? 'bg-destructive/20 text-destructive'
                                      : 'bg-warning/20 text-warning'
                                }`}>
                                  {record.outcome_status || record.status}
                                </div>
                              </div>
                            </div>

                            {/* Expandable data preview */}
                            {isPreviewOpen && hasExtractedCarbon && (
                              <div className="mt-3 p-3 rounded-lg bg-background/60 border border-border/50 text-xs space-y-2">
                                <p className="font-semibold text-foreground mb-1">Extracted Carbon Data Preview</p>
                                <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                                  {record.scope_1_co2e != null && (
                                    <div className="p-2 rounded bg-surface">
                                      <div className="text-muted-foreground">Scope 1 (Direct)</div>
                                      <div className="font-bold text-foreground text-sm">{record.scope_1_co2e.toFixed(2)} tCO₂e</div>
                                    </div>
                                  )}
                                  {record.scope_2_co2e != null && (
                                    <div className="p-2 rounded bg-surface">
                                      <div className="text-muted-foreground">Scope 2 (Indirect)</div>
                                      <div className="font-bold text-foreground text-sm">{record.scope_2_co2e.toFixed(2)} tCO₂e</div>
                                    </div>
                                  )}
                                  {record.scope_3_co2e != null && (
                                    <div className="p-2 rounded bg-surface">
                                      <div className="text-muted-foreground">Scope 3 (Value Chain)</div>
                                      <div className="font-bold text-foreground text-sm">{record.scope_3_co2e.toFixed(2)} tCO₂e</div>
                                    </div>
                                  )}
                                  {record.scope_1_co2e != null && record.scope_2_co2e != null && record.scope_3_co2e != null && (
                                    <div className="p-2 rounded bg-primary/5 border border-primary/20">
                                      <div className="text-muted-foreground">Total</div>
                                      <div className="font-bold text-primary text-sm">
                                        {(record.scope_1_co2e + record.scope_2_co2e + record.scope_3_co2e).toFixed(2)} tCO₂e
                                      </div>
                                    </div>
                                  )}
                                </div>
                                <p className="text-muted-foreground italic mt-1">
                                  Clicking "Apply to Dashboard" will populate Emissions, Scope 3, Improvement Plan, Data Quality and Certification sections.
                                </p>
                              </div>
                            )}

                            <div className="flex items-center gap-3 mt-3 text-xs text-muted-foreground flex-wrap">
                              <span>{record.findings_count ?? 0} findings</span>
                              {(record.major_findings ?? 0) > 0 && (
                                <span className="text-destructive">{record.major_findings} major</span>
                              )}
                              {(record.minor_findings ?? 0) > 0 && (
                                <span className="text-warning">{record.minor_findings} minor</span>
                              )}
                              {(record.observations ?? 0) > 0 && (
                                <span>{record.observations} observations</span>
                              )}
                              <div className="ml-auto flex items-center gap-2 flex-wrap justify-end">
                                {record.import_job_id && (
                                  <button
                                    onClick={() => handleApplyImport(record.import_job_id!)}
                                    disabled={isApplying}
                                    className={`inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed ${
                                      carbonApplied
                                        ? 'bg-surface border border-border text-muted-foreground hover:bg-surface/80 hover:text-foreground'
                                        : 'bg-primary/10 text-primary hover:bg-primary/20'
                                    }`}
                                  >
                                    {isApplying ? (
                                      <><RefreshCw className="w-3 h-3 animate-spin" /> Applying…</>
                                    ) : carbonApplied ? (
                                      <><RefreshCw className="w-3 h-3" /> Re-sync Dashboard</>
                                    ) : (
                                      <><FileUp className="w-3 h-3" /> Apply to Dashboard</>
                                    )}
                                  </button>
                                )}
                                {record.import_job_id && (
                                  <a
                                    href={`/audits/0/import-review?jobId=${record.import_job_id}`}
                                    className="text-primary hover:underline flex items-center gap-1"
                                  >
                                    View Import <ArrowUpRight className="w-3 h-3" />
                                  </a>
                                )}
                              </div>
                            </div>
                          </div>
                        </div>
                      )
                    })}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Certification Tab */}
          {activeTab === 'certification' && (
            <div className="space-y-6">
              {/* Certification Status Panel */}
              {certification && currentYear && (
                <CertificationStatusPanel
                  yearId={currentYear.id}
                  certification={{
                    status: certification.status,
                    certificate_number: null,
                    certification_date: null,
                    expiry_date: null,
                    certifying_body: 'Planet Mark',
                    assessor_name: null,
                    readiness_percent: certification.readiness_percent,
                    data_quality_met: certification.data_quality_met,
                    actions_completed: certification.actions_completed,
                    actions_total: certification.actions_total,
                  }}
                  onUpdated={() => currentYear && loadYearDetails(currentYear.id)}
                />
              )}

              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Evidence checklist (existing) */}
                <div className="bg-card rounded-xl border border-border">
                  <div className="p-4 bg-surface border-b border-border">
                    <h3 className="font-bold text-foreground">{t('planet_mark.evidence_checklist')}</h3>
                    <p className="text-sm text-muted-foreground">
                      {t('planet_mark.evidence_checklist_desc')}
                    </p>
                  </div>
                  <div className="p-4 space-y-2">
                    {(certification?.evidence_checklist ?? []).map((doc) => (
                      <div
                        key={doc.description}
                        className="flex items-center justify-between p-2.5 bg-gray-50 rounded-lg border"
                      >
                        <div className="flex items-center gap-3">
                          {doc.uploaded ? (
                            <CheckCircle2
                              className={`w-5 h-5 ${doc.verified ? 'text-green-500' : 'text-amber-500'}`}
                            />
                          ) : (
                            <AlertTriangle className="w-5 h-5 text-red-400" />
                          )}
                          <span className="text-sm text-gray-800">{doc.description}</span>
                        </div>
                        <span
                          className={`text-xs font-medium ${
                            doc.verified
                              ? 'text-green-600'
                              : doc.uploaded
                                ? 'text-amber-600'
                                : 'text-red-500'
                          }`}
                        >
                          {doc.verified
                            ? t('planet_mark.verified')
                            : doc.uploaded
                              ? t('planet_mark.pending_review')
                              : t('planet_mark.missing')}
                        </span>
                      </div>
                    ))}
                    {!certification && (
                      <div className="text-sm text-gray-400 py-2">
                        Certification evidence will appear once the reporting year has live data.
                      </div>
                    )}
                  </div>
                </div>

                {/* Evidence upload panel */}
                {currentYear && (
                  <div className="bg-card rounded-xl border border-border">
                    <div className="p-4 bg-surface border-b border-border flex items-center justify-between">
                      <div>
                        <h3 className="font-bold text-foreground">Upload Evidence</h3>
                        <p className="text-sm text-muted-foreground">
                          Upload supporting documents for certification
                        </p>
                      </div>
                      <span className="text-xs text-gray-500">{evidenceList.length} uploaded</span>
                    </div>
                    <div className="p-4">
                      <EvidenceUploadRow
                        yearId={currentYear.id}
                        documentType="utility_bill"
                        evidenceCategory="scope_2"
                        label="Electricity Bills (12 months)"
                        description="Upload electricity invoices covering the full reporting period"
                        required
                        onUploaded={() => loadYearDetails(currentYear.id)}
                      />
                      <EvidenceUploadRow
                        yearId={currentYear.id}
                        documentType="utility_bill"
                        evidenceCategory="scope_1"
                        label="Gas Bills (12 months)"
                        description="Upload gas invoices covering the full reporting period"
                        required
                        onUploaded={() => loadYearDetails(currentYear.id)}
                      />
                      <EvidenceUploadRow
                        yearId={currentYear.id}
                        documentType="fuel_card_report"
                        evidenceCategory="scope_1"
                        label="Fleet Fuel Card Statements"
                        description="Full-year fuel card export from your provider"
                        required
                        onUploaded={() => loadYearDetails(currentYear.id)}
                      />
                      <EvidenceUploadRow
                        yearId={currentYear.id}
                        documentType="certificate"
                        evidenceCategory="certification"
                        label="Planet Mark Certificate / Inspection Report"
                        description="Upload your completed certification report or certificate"
                        onUploaded={() => loadYearDetails(currentYear.id)}
                      />
                      <EvidenceUploadRow
                        yearId={currentYear.id}
                        documentType="improvement_action"
                        evidenceCategory="certification"
                        label="Action Plan Evidence"
                        description="Any supporting evidence for completed improvement actions"
                        onUploaded={() => loadYearDetails(currentYear.id)}
                      />

                      {/* Uploaded evidence list */}
                      {evidenceList.length > 0 && (
                        <div className="mt-4">
                          <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
                            All Uploaded Evidence
                          </h4>
                          <div className="space-y-1.5">
                            {evidenceList.map((ev) => (
                              <div
                                key={ev.id}
                                className="flex items-center justify-between text-xs text-gray-600 bg-gray-50 px-3 py-2 rounded border"
                              >
                                <span className="truncate max-w-xs">{ev.document_name}</span>
                                <div className="flex items-center gap-2 flex-shrink-0 ml-2">
                                  <span className={ev.is_verified ? 'text-green-600' : 'text-amber-500'}>
                                    {ev.is_verified ? '✓ Verified' : '⏳ Pending'}
                                  </span>
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}
