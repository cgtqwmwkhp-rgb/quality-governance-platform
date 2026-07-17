import { useState, useEffect, useCallback, useMemo, useRef, type ChangeEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import {
  AlertTriangle,
  Plus,
  Eye,
  Edit2,
  BarChart3,
  Target,
  Layers,
  Activity,
  AlertCircle,
  Filter,
  Download,
  Upload,
  GitBranch,
  Clock,
  User,
} from 'lucide-react'
import { Button } from '../components/ui/Button'
import { Card, CardContent } from '../components/ui/Card'
import { Badge } from '../components/ui/Badge'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../components/ui/Dialog'
import { Input } from '../components/ui/Input'
import { Label } from '../components/ui/Label'
import { Tooltip, TooltipContent, TooltipTrigger } from '../components/ui/Tooltip'
import { auditsApi, getApiErrorMessage, riskRegisterApi } from '../api/client'
import type { RiskRegisterImportReport } from '../api/riskRegisterClient'
import { toast } from '../contexts/ToastContext'
import { useFeatureFlag } from '../hooks/useFeatureFlag'
import { cn } from '../helpers/utils'
import {
  RiskHeatMap,
  type HeatMapData as InteractiveHeatMapData,
  type HeatMapFocusMode,
  type HeatMapRiskDetail,
  type HeatMapScoreType,
  type TopMover,
  type TrendPoint,
} from '../components/risk/RiskHeatMap'

type HeroFilter =
  | 'all'
  | 'critical'
  | 'high'
  | 'medium'
  | 'outside_appetite'
  | 'overdue'

/** Create-only dialog on the list. View/edit detail popup was removed — open `/risk-register/:id`. */
type DetailMode = 'create' | null

function ColumnHeaderTip({ label, tip }: { label: string; tip: string }) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span className="cursor-help border-b border-dotted border-muted-foreground/50">
          {label}
        </span>
      </TooltipTrigger>
      <TooltipContent className="max-w-xs text-left normal-case tracking-normal">
        {tip}
      </TooltipContent>
    </Tooltip>
  )
}

function isReviewOverdue(nextReviewDate: string | null): boolean {
  if (!nextReviewDate) return false
  const due = new Date(nextReviewDate)
  if (Number.isNaN(due.getTime())) return false
  return due.getTime() < Date.now()
}

type MetricValue = number | null

interface RegisterSummary {
  total_risks: MetricValue
  by_level: {
    critical: MetricValue
    high: MetricValue
    medium: MetricValue
    low: MetricValue
  }
  outside_appetite: MetricValue
  overdue_review: MetricValue
  escalated: MetricValue
}

const EMPTY_SUMMARY: RegisterSummary = {
  total_risks: null,
  by_level: { critical: null, high: null, medium: null, low: null },
  outside_appetite: null,
  overdue_review: null,
  escalated: null,
}

function formatMetric(value: MetricValue): string {
  return value == null ? '—' : String(value)
}

/** Canonical residual score bands: low ≤4, medium 5–9, high 10–16, critical ≥17. */
function residualBandFromScore(score: number): { level: string; color: string } {
  if (score > 16) {
    return { level: 'critical', color: 'hsl(var(--destructive))' }
  }
  if (score >= 10) {
    return { level: 'high', color: 'hsl(var(--warning))' }
  }
  if (score >= 5) {
    return { level: 'medium', color: 'hsl(var(--info))' }
  }
  return { level: 'low', color: 'hsl(var(--success))' }
}

/** Matrix cell score bands (likelihood × impact). */
function matrixBandFromScore(score: number): { level: string; color: string } {
  return residualBandFromScore(score)
}

type HeatmapApiCell = {
  likelihood?: number
  impact?: number
  count?: number
  risk_count?: number
  risks?: { id: number; title?: string }[]
  risk_ids?: number[]
  risk_titles?: string[]
}

function flattenHeatmapCells(heatmap: {
  cells?: HeatmapApiCell[]
  matrix?: HeatmapApiCell[][]
}): HeatmapApiCell[] {
  if (Array.isArray(heatmap.cells) && heatmap.cells.length > 0) {
    return heatmap.cells
  }
  if (!Array.isArray(heatmap.matrix)) {
    return []
  }
  return heatmap.matrix.flat()
}

function heatmapBandCounts(cells: HeatmapApiCell[]): Record<string, number> {
  return cells.reduce<Record<string, number>>(
    (counts, cell) => {
      const count = cell.count ?? cell.risk_count
      if (
        typeof cell.likelihood !== 'number' ||
        typeof cell.impact !== 'number' ||
        typeof count !== 'number'
      ) {
        return counts
      }
      const { level } = residualBandFromScore(cell.likelihood * cell.impact)
      counts[level] += count
      return counts
    },
    { critical: 0, high: 0, medium: 0, low: 0 },
  )
}

interface Risk {
  id: number
  reference: string
  title: string
  category: string
  department: string
  inherent_score: number
  inherent_likelihood?: number
  inherent_impact?: number
  residual_score: number
  residual_likelihood?: number
  residual_impact?: number
  risk_level: string
  risk_color: string
  treatment_strategy: string
  status: string
  is_within_appetite: boolean
  risk_owner_name: string
  next_review_date: string | null
  is_escalated?: boolean
  escalation_reason?: string
  linked_audits?: string[]
  linked_actions?: string[]
  linked_incidents?: string[]
  suggestion_triage_status?: string | null
  created_at?: string
}

type HeatMapData = InteractiveHeatMapData

interface LinkedAuditTarget {
  kind: 'audit' | 'finding'
  path: string
}

function normalizeLinkedReference(reference: string): string {
  return reference.trim().toLowerCase()
}

const CATEGORIES = [
  { id: 'strategic', label: 'Strategic', color: 'bg-primary' },
  { id: 'operational', label: 'Operational', color: 'bg-info' },
  { id: 'financial', label: 'Financial', color: 'bg-success' },
  { id: 'compliance', label: 'Compliance', color: 'bg-warning' },
  { id: 'reputational', label: 'Reputational', color: 'bg-destructive' },
  { id: 'health_safety', label: 'Health & Safety', color: 'bg-destructive' },
  { id: 'environmental', label: 'Environmental', color: 'bg-success' },
]

const TREATMENT_STRATEGIES = [
  { id: 'treat', label: 'Treat', icon: '🛠️' },
  { id: 'tolerate', label: 'Tolerate', icon: '✅' },
  { id: 'transfer', label: 'Transfer', icon: '↗️' },
  { id: 'terminate', label: 'Terminate', icon: '🚫' },
]

export default function RiskRegister() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const bowtieEnabled = useFeatureFlag('risk_bowtie')
  const [view, setView] = useState<'register' | 'heatmap' | 'bowtie'>('register')
  const [risks, setRisks] = useState<Risk[]>([])
  const [heatMapData, setHeatMapData] = useState<HeatMapData | null>(null)
  const [detailMode, setDetailMode] = useState<DetailMode>(null)
  const [ownerDraft, setOwnerDraft] = useState('')
  const [titleDraft, setTitleDraft] = useState('')
  const [descriptionDraft, setDescriptionDraft] = useState('')
  const [categoryDraft, setCategoryDraft] = useState('operational')
  const [detailSaving, setDetailSaving] = useState(false)
  const [heroFilter, setHeroFilter] = useState<HeroFilter>(
    (searchParams.get('hero') as HeroFilter) || 'all',
  )
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [summaryUnavailable, setSummaryUnavailable] = useState(false)
  const [heatmapUnavailable, setHeatmapUnavailable] = useState(false)
  const [auditLinksUnavailable, setAuditLinksUnavailable] = useState(false)
  const [showFilters, setShowFilters] = useState(false)
  const [auditOnly, setAuditOnly] = useState(searchParams.get('auditOnly') === '1')
  const [auditRefFilter, setAuditRefFilter] = useState(searchParams.get('auditRef') || '')
  const focusRiskId = Number(searchParams.get('riskId') || '')
  const nearMissRefFilter = (searchParams.get('nearMissRef') || '').trim()
  const [summary, setSummary] = useState<RegisterSummary>(EMPTY_SUMMARY)
  const [registerMode, setRegisterMode] = useState<'active' | 'import_triage'>('active')
  const [pendingTriageCount, setPendingTriageCount] = useState(0)
  const [rejectDialogOpen, setRejectDialogOpen] = useState(false)
  const [rejectTargetId, setRejectTargetId] = useState<number | null>(null)
  const [rejectNotes, setRejectNotes] = useState('')
  const [triageSubmitting, setTriageSubmitting] = useState(false)
  const [linkedAuditTargets, setLinkedAuditTargets] = useState<Record<string, LinkedAuditTarget>>({})
  const [filterCategory, setFilterCategory] = useState(searchParams.get('category') || '')
  const [filterDepartment, setFilterDepartment] = useState(searchParams.get('department') || '')
  const [filterStatus, setFilterStatus] = useState(searchParams.get('status') || '')
  const [scoreType, setScoreType] = useState<HeatMapScoreType>(
    (searchParams.get('scoreType') as HeatMapScoreType) || 'residual',
  )
  const [focusMode, setFocusMode] = useState<HeatMapFocusMode>('none')
  const [cellFilter, setCellFilter] = useState<{ likelihood: number; impact: number } | null>(() => {
    const L = Number(searchParams.get('L') || '')
    const I = Number(searchParams.get('I') || '')
    return Number.isInteger(L) && L >= 1 && L <= 5 && Number.isInteger(I) && I >= 1 && I <= 5
      ? { likelihood: L, impact: I }
      : null
  })
  const [trends, setTrends] = useState<TrendPoint[]>([])
  const [topMovers, setTopMovers] = useState<TopMover[]>([])
  const importFileInputRef = useRef<HTMLInputElement>(null)
  const [importDialogOpen, setImportDialogOpen] = useState(false)
  const [importFile, setImportFile] = useState<File | null>(null)
  const [importReport, setImportReport] = useState<RiskRegisterImportReport | null>(null)
  const [importBusy, setImportBusy] = useState(false)

  useEffect(() => {
    if (searchParams.get('triage') === 'import') {
      setRegisterMode('import_triage')
      setView('register')
    }
  }, [searchParams])

  useEffect(() => {
    const next = new URLSearchParams(searchParams)
    if (auditOnly) next.set('auditOnly', '1')
    else next.delete('auditOnly')
    if (auditRefFilter) next.set('auditRef', auditRefFilter)
    else next.delete('auditRef')
    if (filterCategory) next.set('category', filterCategory)
    else next.delete('category')
    if (filterDepartment) next.set('department', filterDepartment)
    else next.delete('department')
    if (filterStatus) next.set('status', filterStatus)
    else next.delete('status')
    if (scoreType && scoreType !== 'residual') next.set('scoreType', scoreType)
    else next.delete('scoreType')
    if (cellFilter) {
      next.set('L', String(cellFilter.likelihood))
      next.set('I', String(cellFilter.impact))
    } else {
      next.delete('L')
      next.delete('I')
    }
    if (view !== 'register') next.set('view', view)
    else next.delete('view')
    if (heroFilter && heroFilter !== 'all') next.set('hero', heroFilter)
    else next.delete('hero')
    const nextQuery = next.toString()
    if (nextQuery !== searchParams.toString()) {
      setSearchParams(next, { replace: true })
    }
  }, [
    auditOnly,
    auditRefFilter,
    filterCategory,
    filterDepartment,
    filterStatus,
    scoreType,
    cellFilter,
    view,
    heroFilter,
    searchParams,
    setSearchParams,
  ])

  const workspaceFilters = useMemo(
    () => ({
      category: filterCategory || undefined,
      department: filterDepartment || undefined,
      status: filterStatus || undefined,
    }),
    [filterCategory, filterDepartment, filterStatus],
  )

  const loadRisks = useCallback(async () => {
    setLoading(true)
    setLoadError(null)
    setSummaryUnavailable(false)
    setHeatmapUnavailable(false)
    setAuditLinksUnavailable(false)
    try {
      const bandParams =
        cellFilter != null
          ? scoreType === 'inherent'
            ? {
                inherent_likelihood: cellFilter.likelihood,
                inherent_impact: cellFilter.impact,
              }
            : {
                residual_likelihood: cellFilter.likelihood,
                residual_impact: cellFilter.impact,
              }
          : {}
      const listParams =
        registerMode === 'import_triage'
          ? ({ limit: 100, suggestion_triage: 'pending' as const, ...workspaceFilters })
          : ({
              limit: cellFilter ? 200 : 100,
              ...workspaceFilters,
              ...bandParams,
            })
      const [risksResult, summaryResult, heatmapResult, pendingResult, trendsResult] =
        await Promise.allSettled([
          riskRegisterApi.list(listParams),
          riskRegisterApi.getSummary(workspaceFilters),
          riskRegisterApi.getHeatmap({ ...workspaceFilters, score_type: scoreType }),
          riskRegisterApi.list({ limit: 1, suggestion_triage: 'pending' }),
          riskRegisterApi.getTrends(365, true),
        ])

      if (risksResult.status === 'rejected') {
        const message = getApiErrorMessage(
          risksResult.reason,
          'Risk register unavailable — could not load risks.',
        )
        setLoadError(message)
        setRisks([])
        setSummary(EMPTY_SUMMARY)
        setSummaryUnavailable(true)
        setHeatMapData(null)
        setHeatmapUnavailable(true)
        setPendingTriageCount(0)
        setLinkedAuditTargets({})
        toast.error(message)
        return
      }

      const risksResponse = risksResult.value
      const apiRisks = risksResponse.data?.items ?? []
      const mappedRisks: Risk[] = apiRisks.map((r) => {
        const residual = r.residual_score ?? r.risk_score ?? 0
        const inherent = r.inherent_score ?? r.risk_score ?? 0
        const { level: riskLevel, color: riskColor } = residualBandFromScore(residual)

        return {
          id: r.id,
          reference: r.reference ?? (r.title ? `RISK-${String(r.id).padStart(4, '0')}` : `RISK-${r.id}`),
          title: r.title,
          category: r.category ?? 'operational',
          department: r.department ?? '',
          inherent_score: inherent,
          inherent_likelihood: r.inherent_likelihood,
          inherent_impact: r.inherent_impact,
          residual_score: residual,
          residual_likelihood: r.residual_likelihood,
          residual_impact: r.residual_impact,
          risk_level: riskLevel,
          risk_color: riskColor,
          treatment_strategy: r.treatment_strategy ?? 'treat',
          status: r.status ?? 'monitoring',
          is_within_appetite: r.is_within_appetite ?? true,
          risk_owner_name: r.risk_owner_name ?? r.risk_owner ?? '',
          next_review_date: r.next_review_date ?? r.review_date ?? null,
          is_escalated: r.is_escalated ?? false,
          escalation_reason: r.escalation_reason,
          linked_audits: r.linked_audits ?? [],
          linked_actions: r.linked_actions ?? [],
          linked_incidents: r.linked_incidents ?? [],
          suggestion_triage_status: r.suggestion_triage_status ?? null,
          created_at: r.created_at,
        }
      })
      setRisks(mappedRisks)

      if (pendingResult.status === 'fulfilled') {
        const pendingTotal = pendingResult.value.data?.total
        setPendingTriageCount(typeof pendingTotal === 'number' ? pendingTotal : 0)
      } else {
        setPendingTriageCount(0)
      }

      if (summaryResult.status === 'fulfilled') {
        const s = summaryResult.value.data as
          | {
              total_risks?: number
              critical?: number
              high?: number
              medium?: number
              low?: number
              by_level?: { critical?: number; high?: number; medium?: number; low?: number }
              outside_appetite?: number
              overdue_review?: number
              escalated?: number
            }
          | undefined
        const byLevel = s?.by_level
        const heatmapCells =
          heatmapResult.status === 'fulfilled'
            ? flattenHeatmapCells(heatmapResult.value.data ?? {})
            : []
        const fallbackBandCounts =
          heatmapResult.status === 'fulfilled' ? heatmapBandCounts(heatmapCells) : null
        setSummary({
          total_risks: typeof s?.total_risks === 'number' ? s.total_risks : null,
          by_level: {
            critical:
              typeof byLevel?.critical === 'number'
                ? byLevel.critical
                : typeof s?.critical === 'number'
                  ? s.critical
                  : fallbackBandCounts?.critical ?? null,
            high:
              typeof byLevel?.high === 'number'
                ? byLevel.high
                : typeof s?.high === 'number'
                  ? s.high
                  : fallbackBandCounts?.high ?? null,
            medium:
              typeof byLevel?.medium === 'number'
                ? byLevel.medium
                : typeof s?.medium === 'number'
                  ? s.medium
                  : fallbackBandCounts?.medium ?? null,
            low:
              typeof byLevel?.low === 'number'
                ? byLevel.low
                : typeof s?.low === 'number'
                  ? s.low
                  : fallbackBandCounts?.low ?? null,
          },
          outside_appetite:
            typeof s?.outside_appetite === 'number'
              ? s.outside_appetite
              : mappedRisks.filter((risk) => risk.is_within_appetite === false).length,
          // Never invent overdue_review — API supplies it; null means unavailable.
          overdue_review: typeof s?.overdue_review === 'number' ? s.overdue_review : null,
          escalated:
            typeof s?.escalated === 'number'
              ? s.escalated
              : mappedRisks.filter((risk) => risk.is_escalated).length,
        })
        setSummaryUnavailable(false)
      } else {
        setSummary(EMPTY_SUMMARY)
        setSummaryUnavailable(true)
        toast.warning('Risk summary metrics unavailable — counts are not shown as zero.')
      }

      if (heatmapResult.status === 'fulfilled' && Array.isArray(heatmapResult.value.data?.matrix)) {
        const heatmap = heatmapResult.value.data
        const apiSummary = heatmap.summary
        setHeatMapData({
          matrix: heatmap.matrix.map((row) =>
            row.map((cell) => ({
              likelihood: cell.likelihood,
              impact: cell.impact,
              score: cell.score ?? cell.likelihood * cell.impact,
              level: cell.level ?? matrixBandFromScore(cell.likelihood * cell.impact).level,
              color: cell.color ?? matrixBandFromScore(cell.likelihood * cell.impact).color,
              risk_count: cell.risk_count ?? cell.count ?? 0,
              risk_ids: cell.risk_ids ?? cell.risks?.map((r) => r.id) ?? [],
              risk_titles: cell.risk_titles ?? cell.risks?.map((r) => r.title ?? '') ?? [],
              owners_sample: cell.owners_sample ?? [],
              overdue_count: cell.overdue_count ?? 0,
              outside_appetite_count: cell.outside_appetite_count ?? 0,
              intensity: cell.intensity ?? 0,
              above_appetite_band: cell.above_appetite_band ?? false,
              movers: cell.movers ?? [],
            })),
          ),
          summary: {
            total_risks: apiSummary?.total_risks ?? 0,
            critical_risks: apiSummary?.critical_risks ?? 0,
            high_risks: apiSummary?.high_risks ?? 0,
            medium_risks: apiSummary?.medium_risks,
            low_risks: apiSummary?.low_risks,
            outside_appetite: apiSummary?.outside_appetite ?? 0,
            average_inherent_score: apiSummary?.average_inherent_score ?? 0,
            average_residual_score: apiSummary?.average_residual_score ?? 0,
          },
          likelihood_labels: heatmap.likelihood_labels ?? {
            1: 'Rare',
            2: 'Unlikely',
            3: 'Possible',
            4: 'Likely',
            5: 'Almost Certain',
          },
          impact_labels: heatmap.impact_labels ?? {
            1: 'Insignificant',
            2: 'Minor',
            3: 'Moderate',
            4: 'Major',
            5: 'Catastrophic',
          },
          appetite_overlay: heatmap.appetite_overlay,
          view_mode: heatmap.view_mode,
        })
        setHeatmapUnavailable(false)
      } else {
        setHeatMapData(null)
        setHeatmapUnavailable(true)
        toast.warning('Risk heat map unavailable.')
      }

      if (trendsResult.status === 'fulfilled') {
        const raw = trendsResult.value.data
        if (Array.isArray(raw)) {
          setTrends(raw as TrendPoint[])
          setTopMovers([])
        } else if (raw && typeof raw === 'object') {
          const body = raw as { series?: TrendPoint[]; top_movers?: TopMover[] }
          setTrends(Array.isArray(body.series) ? body.series : [])
          setTopMovers(Array.isArray(body.top_movers) ? body.top_movers : [])
        } else {
          setTrends([])
          setTopMovers([])
        }
      } else {
        setTrends([])
        setTopMovers([])
      }

      const [runsResult, findingsResult] = await Promise.allSettled([
        auditsApi.listRuns(1, 100),
        auditsApi.listFindings(1, 100),
      ])
      const nextLinkedAuditTargets: Record<string, LinkedAuditTarget> = {}
      if (runsResult.status === 'fulfilled') {
        for (const run of runsResult.value.data?.items ?? []) {
          const isExternalImport =
            run.is_external_audit_import === true || run.is_external_import_intake === true
          nextLinkedAuditTargets[normalizeLinkedReference(run.reference_number)] = {
            kind: 'audit',
            path: `/audits/${run.id}/${isExternalImport ? 'import-review' : 'execute'}`,
          }
        }
      }
      if (findingsResult.status === 'fulfilled') {
        for (const finding of findingsResult.value.data?.items ?? []) {
          nextLinkedAuditTargets[normalizeLinkedReference(finding.reference_number)] = {
            kind: 'finding',
            path: `/audits?view=findings&findingId=${encodeURIComponent(finding.id)}`,
          }
        }
      }
      setLinkedAuditTargets(nextLinkedAuditTargets)
      if (runsResult.status === 'rejected' && findingsResult.status === 'rejected') {
        setAuditLinksUnavailable(true)
        toast.warning('Audit deep-links unavailable — linked references shown as plain text.')
      }
    } catch (err) {
      const message = getApiErrorMessage(err, 'Risk register unavailable.')
      console.error('Failed to load risk register data:', err)
      setLoadError(message)
      setRisks([])
      setSummary(EMPTY_SUMMARY)
      setSummaryUnavailable(true)
      setHeatMapData(null)
      setHeatmapUnavailable(true)
      toast.error(message)
    } finally {
      setLoading(false)
    }
  }, [registerMode, workspaceFilters, cellFilter, scoreType])

  useEffect(() => {
    void loadRisks()
  }, [loadRisks])

  const heatmapRiskDetails = useMemo(() => {
    const map = new Map<number, HeatMapRiskDetail>()
    for (const risk of risks) {
      map.set(risk.id, {
        id: risk.id,
        title: risk.title,
        reference: risk.reference,
        created_at: risk.created_at,
        category: risk.category,
        owner: risk.risk_owner_name || undefined,
        inherent_score: risk.inherent_score,
        residual_score: risk.residual_score,
        status: risk.status,
        next_review_date: risk.next_review_date,
      })
    }
    return map
  }, [risks])

  const resolveImportTriage = async (
    riskId: number,
    decision: 'accept' | 'reject',
    notes?: string,
  ) => {
    try {
      setTriageSubmitting(true)
      const trimmed = notes?.trim()
      await riskRegisterApi.resolveSuggestionTriage(riskId, {
        decision,
        ...(trimmed ? { notes: trimmed } : {}),
      })
      await loadRisks()
      toast.success(
        decision === 'accept'
          ? t('risk_register.import_triage_toast_accept')
          : t('risk_register.import_triage_toast_reject'),
      )
    } catch (err) {
      console.error('Import triage resolution failed:', err)
      toast.error(t('risk_register.import_triage_toast_error'))
    } finally {
      setTriageSubmitting(false)
    }
  }

  const openRejectDialog = (riskId: number) => {
    setRejectTargetId(riskId)
    setRejectNotes('')
    setRejectDialogOpen(true)
  }

  const closeRejectDialog = () => {
    setRejectDialogOpen(false)
    setRejectTargetId(null)
    setRejectNotes('')
  }

  const confirmRejectWithNotes = async () => {
    if (rejectTargetId == null) return
    await resolveImportTriage(rejectTargetId, 'reject', rejectNotes)
    closeRejectDialog()
  }

  const openRiskProfile = (riskId: number) => {
    navigate(`/risk-register/${riskId}`)
  }

  const closeCreateDialog = () => {
    if (detailSaving) return
    setDetailMode(null)
  }

  const openCreateRisk = () => {
    setDetailMode('create')
    setOwnerDraft('')
    setTitleDraft('')
    setDescriptionDraft('')
    setCategoryDraft('operational')
  }

  const saveCreateRisk = async () => {
    if (titleDraft.trim().length < 5) {
      toast.error('Title must be at least 5 characters')
      return
    }
    if (descriptionDraft.trim().length < 10) {
      toast.error('Description must be at least 10 characters')
      return
    }
    setDetailSaving(true)
    try {
      const created = await riskRegisterApi.create({
        title: titleDraft.trim(),
        description: descriptionDraft.trim(),
        category: categoryDraft,
        risk_owner_name: ownerDraft.trim() || undefined,
        inherent_likelihood: 2,
        inherent_impact: 2,
        residual_likelihood: 1,
        residual_impact: 2,
        treatment_strategy: 'treat',
      })
      toast.success('Risk created')
      setDetailMode(null)
      const newId = created.data?.id
      if (typeof newId === 'number' && newId > 0) {
        navigate(`/risk-register/${newId}`)
        return
      }
      await loadRisks()
    } catch (error) {
      toast.error(getApiErrorMessage(error, 'Could not create risk'))
    } finally {
      setDetailSaving(false)
    }
  }

  // Legacy list deep-link `?riskId=` → full Risk Profile page (no detail popup).
  useEffect(() => {
    if (Number.isInteger(focusRiskId) && focusRiskId > 0) {
      navigate(`/risk-register/${focusRiskId}`, { replace: true })
    }
  }, [focusRiskId, navigate])

  const exportRegisterCsv = () => {
    const rows = visibleRisks.map((r) => [
      r.reference,
      r.title,
      r.category,
      String(r.inherent_score),
      String(r.residual_score),
      r.risk_level,
      r.treatment_strategy,
      r.risk_owner_name || '',
      r.status,
    ])
    const header = [
      'reference',
      'title',
      'category',
      'inherent_gross',
      'residual_net',
      'level',
      'treatment',
      'owner',
      'status',
    ]
    const escape = (value: string) => `"${value.replace(/"/g, '""')}"`
    const csv = [header, ...rows]
      .map((cols) => cols.map((c) => escape(String(c))).join(','))
      .join('\n')
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `risk-register-${registerMode}-${new Date().toISOString().slice(0, 10)}.csv`
    a.click()
    URL.revokeObjectURL(url)
    toast.success(`Exported ${visibleRisks.length} risk${visibleRisks.length === 1 ? '' : 's'}`)
  }

  const resetImportDialog = () => {
    setImportDialogOpen(false)
    setImportFile(null)
    setImportReport(null)
    setImportBusy(false)
    if (importFileInputRef.current) {
      importFileInputRef.current.value = ''
    }
  }

  const runImportDryRun = async (file: File) => {
    setImportBusy(true)
    setImportReport(null)
    try {
      const { data } = await riskRegisterApi.importDryRun(file)
      setImportReport(data)
      setImportDialogOpen(true)
    } catch (error) {
      toast.error(getApiErrorMessage(error, t('risk_register.excel_import.error_dry_run')))
    } finally {
      setImportBusy(false)
    }
  }

  const handleImportFileSelected = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) return
    setImportFile(file)
    void runImportDryRun(file)
  }

  const commitExcelImport = async () => {
    if (!importFile || !importReport?.ok) return
    setImportBusy(true)
    try {
      const { data } = await riskRegisterApi.importCommit(importFile)
      toast.success(
        t('risk_register.excel_import.toast_commit', {
          created: data.created_count,
          updated: data.updated_count,
        }),
      )
      resetImportDialog()
      await loadRisks()
    } catch (error) {
      toast.error(getApiErrorMessage(error, t('risk_register.excel_import.error_commit')))
    } finally {
      setImportBusy(false)
    }
  }

  const toggleHeroFilter = (next: HeroFilter) => {
    setView('register')
    setHeroFilter((prev) => (prev === next ? 'all' : next))
  }

  const visibleRisks = risks.filter((risk) => {
    const auditLinked = (risk.linked_audits?.length ?? 0) > 0 || (risk.linked_actions?.length ?? 0) > 0 || risk.is_escalated
    if (auditOnly && !auditLinked) {
      return false
    }
    if (auditRefFilter) {
      const needle = auditRefFilter.toLowerCase()
      const linkedAudits = (risk.linked_audits ?? []).map((value) => String(value).toLowerCase())
      if (!linkedAudits.some((value) => value.includes(needle))) {
        return false
      }
    }
    if (nearMissRefFilter) {
      const needle = nearMissRefFilter.toLowerCase()
      const linkedCases = (risk.linked_incidents ?? []).map((value) => String(value).toLowerCase())
      if (!linkedCases.some((value) => value.includes(needle))) {
        return false
      }
    }
    if (heroFilter === 'critical' && risk.risk_level !== 'critical') return false
    if (heroFilter === 'high' && risk.risk_level !== 'high') return false
    if (heroFilter === 'medium' && risk.risk_level !== 'medium') return false
    if (heroFilter === 'outside_appetite' && risk.is_within_appetite !== false) return false
    if (heroFilter === 'overdue' && !isReviewOverdue(risk.next_review_date)) return false
    return true
  })

  const getRiskLevelBadge = (level: string) => {
    const variants: Record<string, 'destructive' | 'warning' | 'info' | 'resolved'> = {
      critical: 'destructive',
      high: 'warning',
      medium: 'info',
      low: 'resolved',
    }
    return (
      <Badge variant={variants[level] || 'default'} className="uppercase">
        {level}
      </Badge>
    )
  }

  const getTreatmentBadge = (strategy: string) => {
    const s = TREATMENT_STRATEGIES.find((t) => t.id === strategy)
    return (
      <span className="px-2 py-1 bg-muted rounded-full text-xs">
        {s?.icon} {s?.label}
      </span>
    )
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary"></div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* IA consolidation notice: /risks redirects here */}
      <div
        className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-950"
        role="status"
      >
        <p className="font-medium">Single Risk Register</p>
        <p className="mt-1 text-amber-900/90">
          Operational Risks (<code className="text-xs">/risks</code>) now redirects here. Use this
          Enterprise Risk Register as the canonical risk workspace. Legacy operational risk APIs are
          unchanged.
        </p>
      </div>

      {loadError ? (
        <div
          className="rounded-lg border border-destructive/40 bg-destructive/10 px-4 py-3 text-sm text-destructive"
          role="alert"
          data-testid="risk-register-load-error"
        >
          <p className="font-medium">Risk register unavailable</p>
          <p className="mt-1">{loadError}</p>
          <p className="mt-1 text-destructive/90">
            Counts and the register table are not shown as empty zeros while the API is unavailable.
          </p>
          <Button
            size="sm"
            variant="secondary"
            className="mt-3"
            onClick={() => void loadRisks()}
            data-testid="risk-register-retry"
          >
            Retry
          </Button>
        </div>
      ) : null}

      {!loadError && (summaryUnavailable || heatmapUnavailable || auditLinksUnavailable) ? (
        <div
          className="rounded-lg border border-warning/40 bg-warning/10 px-4 py-3 text-sm text-warning-foreground"
          role="status"
          data-testid="risk-register-partial-badge"
        >
          <p className="font-medium">Partial data — some sources unavailable</p>
          <ul className="mt-1 list-disc pl-5 text-foreground/90">
            {summaryUnavailable ? (
              <li>Summary metrics unavailable (not shown as fake zeros)</li>
            ) : null}
            {heatmapUnavailable ? <li>Heat map unavailable</li> : null}
            {auditLinksUnavailable ? (
              <li>Audit deep-links unavailable — references remain as plain text</li>
            ) : null}
          </ul>
        </div>
      ) : null}

      {!loadError && !summaryUnavailable ? (
        <div
          className="sr-only"
          data-testid="risk-register-live-badge"
          aria-live="polite"
        >
          Live data
        </div>
      ) : null}

      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-foreground mb-2">Enterprise Risk Register</h1>
          <p className="text-muted-foreground">ISO 31000 Compliant Risk Management</p>
          <div className="flex flex-wrap gap-2 mt-3">
            <Button
              size="sm"
              variant={registerMode === 'active' ? 'default' : 'secondary'}
              onClick={() => {
                setRegisterMode('active')
                const next = new URLSearchParams(searchParams)
                next.delete('triage')
                if (next.toString() !== searchParams.toString()) {
                  setSearchParams(next, { replace: true })
                }
              }}
            >
              Active register
            </Button>
            <Button
              size="sm"
              variant={registerMode === 'import_triage' ? 'default' : 'secondary'}
              onClick={() => {
                setRegisterMode('import_triage')
                setView('register')
                const next = new URLSearchParams(searchParams)
                next.set('triage', 'import')
                setSearchParams(next, { replace: true })
              }}
            >
              Import triage
              {pendingTriageCount > 0 ? ` (${pendingTriageCount})` : ''}
            </Button>
          </div>
          {registerMode === 'import_triage' ? (
            <p className="text-xs text-muted-foreground mt-2 max-w-2xl">
              Risks raised from external audit import appear here until you accept them into the live register
              or reject them (closed, auditable). Corrective actions (CAPA) linked from the same findings stay in
              CAPA as usual—only register suggestions are triaged here.
            </p>
          ) : null}
        </div>
        <div className="flex gap-3">
          <Button
            variant="secondary"
            onClick={() => setShowFilters(!showFilters)}
            data-testid="risk-filters-toggle"
          >
            <Filter className="w-4 h-4" />
            Filters
          </Button>
          <Button
            variant="secondary"
            onClick={exportRegisterCsv}
            data-testid="risk-export-csv"
          >
            <Download className="w-4 h-4" />
            Export
          </Button>
          {registerMode === 'active' ? (
            <>
              <input
                ref={importFileInputRef}
                type="file"
                accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                className="sr-only"
                aria-label={t('risk_register.excel_import.button')}
                data-testid="risk-import-xlsx-input"
                onChange={handleImportFileSelected}
              />
              <Button
                variant="secondary"
                disabled={importBusy}
                onClick={() => importFileInputRef.current?.click()}
                data-testid="risk-import-xlsx-button"
              >
                <Upload className="w-4 h-4" />
                {importBusy ? t('risk_register.excel_import.validating') : t('risk_register.excel_import.button')}
              </Button>
            </>
          ) : null}
          <Button onClick={openCreateRisk} data-testid="risk-add-button">
            <Plus className="w-4 h-4" />
            Add Risk
          </Button>
        </div>
      </div>

      {showFilters ? (
        <Card>
          <CardContent className="flex flex-col gap-3 p-4">
            <div className="flex flex-col gap-3 md:flex-row md:flex-wrap md:items-center">
              <select
                value={filterCategory}
                onChange={(e) => setFilterCategory(e.target.value)}
                className="h-10 rounded-md border border-input bg-background px-3 text-sm"
                data-testid="risk-filter-category"
              >
                <option value="">All categories</option>
                {CATEGORIES.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.label}
                  </option>
                ))}
              </select>
              <input
                type="text"
                value={filterDepartment}
                onChange={(e) => setFilterDepartment(e.target.value)}
                placeholder="Department"
                className="h-10 rounded-md border border-input bg-background px-3 text-sm"
                data-testid="risk-filter-department"
              />
              <select
                value={filterStatus}
                onChange={(e) => setFilterStatus(e.target.value)}
                className="h-10 rounded-md border border-input bg-background px-3 text-sm"
                data-testid="risk-filter-status"
              >
                <option value="">All statuses (excl. closed)</option>
                <option value="active">Active</option>
                <option value="monitoring">Monitoring</option>
                <option value="mitigated">Mitigated</option>
                <option value="draft">Draft</option>
              </select>
              <Button
                variant={auditOnly ? 'default' : 'secondary'}
                onClick={() => setAuditOnly((prev) => !prev)}
              >
                Audit-origin only
              </Button>
              <input
                type="text"
                value={auditRefFilter}
                onChange={(e) => setAuditRefFilter(e.target.value)}
                placeholder="Filter by audit reference"
                className="h-10 rounded-md border border-input bg-background px-3 text-sm"
              />
            </div>
            {(auditOnly ||
              auditRefFilter ||
              filterCategory ||
              filterDepartment ||
              filterStatus ||
              cellFilter ||
              heroFilter !== 'all') && (
              <Button
                variant="ghost"
                onClick={() => {
                  setAuditOnly(false)
                  setAuditRefFilter('')
                  setFilterCategory('')
                  setFilterDepartment('')
                  setFilterStatus('')
                  setCellFilter(null)
                  setHeroFilter('all')
                }}
              >
                Clear filters
              </Button>
            )}
          </CardContent>
        </Card>
      ) : null}

      {heroFilter !== 'all' && (
        <div
          className="flex items-center gap-2 rounded-lg border border-primary/30 bg-primary/5 px-3 py-2 text-sm"
          data-testid="risk-hero-filter-chip"
        >
          <Badge variant="default">Hero filter</Badge>
          <span className="text-foreground capitalize">{heroFilter.replace('_', ' ')}</span>
          <Button size="sm" variant="ghost" onClick={() => setHeroFilter('all')}>
            Clear
          </Button>
        </div>
      )}

      {/* Summary Cards — clickable filters (Active + Import triage) */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4" data-testid="risk-summary-cards">
        {(
          [
            {
              key: 'all' as const,
              label: 'Total Risks',
              value: summary.total_risks,
              testId: 'risk-metric-total',
              icon: <Layers className="w-5 h-5 text-info" />,
              iconWrap: 'bg-info/20',
              valueClass: 'text-foreground',
              cardClass: '',
            },
            {
              key: 'critical' as const,
              label: 'Critical',
              value: summary.by_level.critical,
              testId: 'risk-metric-critical',
              icon: <AlertTriangle className="w-5 h-5 text-destructive" />,
              iconWrap: 'bg-destructive/20',
              valueClass: 'text-destructive',
              cardClass: 'border-destructive/30',
            },
            {
              key: 'high' as const,
              label: 'High',
              value: summary.by_level.high,
              testId: 'risk-metric-high',
              icon: <AlertCircle className="w-5 h-5 text-warning" />,
              iconWrap: 'bg-warning/20',
              valueClass: 'text-warning',
              cardClass: 'border-warning/30',
            },
            {
              key: 'medium' as const,
              label: 'Medium',
              value: summary.by_level.medium,
              testId: 'risk-metric-medium',
              icon: <Activity className="w-5 h-5 text-info" />,
              iconWrap: 'bg-info/20',
              valueClass: 'text-info',
              cardClass: 'border-info/30',
            },
            {
              key: 'outside_appetite' as const,
              label: 'Outside Appetite',
              value: summary.outside_appetite,
              testId: 'risk-metric-outside-appetite',
              icon: <Target className="w-5 h-5 text-primary" />,
              iconWrap: 'bg-primary/20',
              valueClass: 'text-primary',
              cardClass: 'border-primary/30',
            },
            {
              key: 'overdue' as const,
              label: 'Overdue Review',
              value: summary.overdue_review,
              testId: 'risk-metric-overdue-review',
              icon: <Clock className="w-5 h-5 text-muted-foreground" />,
              iconWrap: 'bg-muted',
              valueClass: 'text-foreground',
              cardClass: '',
              unavailableLabel: 'Overdue review unavailable',
            },
          ] as const
        ).map((card) => {
          const active = heroFilter === card.key
          const unavailable = card.value == null
          const unavailableLabel =
            'unavailableLabel' in card && card.unavailableLabel
              ? card.unavailableLabel
              : `${card.label} unavailable`
          return (
            <Card
              key={card.key}
              className={cn(
                card.cardClass,
                'transition-all',
                unavailable
                  ? 'opacity-70'
                  : 'cursor-pointer hover:border-primary/50 focus-within:ring-2 focus-within:ring-ring',
                active && 'ring-2 ring-primary border-primary/40',
              )}
            >
              <CardContent className="p-0">
                <button
                  type="button"
                  className="w-full p-4 text-left disabled:cursor-not-allowed"
                  disabled={unavailable}
                  aria-pressed={active}
                  data-testid={`risk-hero-filter-${card.key}`}
                  onClick={() => toggleHeroFilter(card.key)}
                >
                  <div className="mb-2 flex items-center gap-3">
                    <div className={cn('rounded-lg p-2', card.iconWrap)}>{card.icon}</div>
                    <span
                      className={cn('text-2xl font-bold', card.valueClass)}
                      data-testid={card.testId}
                      aria-label={unavailable ? unavailableLabel : undefined}
                    >
                      {formatMetric(card.value)}
                    </span>
                  </div>
                  <p className="text-sm text-muted-foreground">
                    {unavailable && card.key === 'overdue'
                      ? 'Overdue Review (unavailable)'
                      : card.label}
                  </p>
                  <p className="mt-1 text-[11px] text-muted-foreground">
                    {unavailable ? 'Unavailable' : active ? 'Filter on — click to clear' : 'Click to filter'}
                  </p>
                </button>
              </CardContent>
            </Card>
          )
        })}
      </div>

      {/* View Toggle */}
      <div className="flex gap-2">
        <Button
          variant={view === 'register' ? 'default' : 'secondary'}
          onClick={() => setView('register')}
        >
          <Layers className="w-4 h-4" />
          Risk Register
        </Button>
        <Button
          variant={view === 'heatmap' ? 'default' : 'secondary'}
          onClick={() => setView('heatmap')}
        >
          <BarChart3 className="w-4 h-4" />
          Heat Map
        </Button>
        {bowtieEnabled && (
          <Button
            variant={view === 'bowtie' ? 'default' : 'secondary'}
            onClick={() => setView('bowtie')}
          >
            <GitBranch className="w-4 h-4" />
            Bow-Tie Analysis
          </Button>
        )}
      </div>

      {/* Register View */}
      {view === 'register' && (
        <Card>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-muted/50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground uppercase">
                    <ColumnHeaderTip
                      label="Reference"
                      tip="Stable risk ID used in audits, CAPA, and deep-links."
                    />
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground uppercase">
                    <ColumnHeaderTip
                      label="Risk Title"
                      tip="Short description of the risk event or condition being managed."
                    />
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground uppercase">
                    <ColumnHeaderTip
                      label="Category"
                      tip="Risk taxonomy bucket (e.g. Compliance, Operational, H&S)."
                    />
                  </th>
                  <th className="px-4 py-3 text-center text-xs font-semibold text-muted-foreground uppercase">
                    <ColumnHeaderTip
                      label="Inherent (Gross)"
                      tip="Gross risk score before controls — inherent likelihood × impact."
                    />
                  </th>
                  <th className="px-4 py-3 text-center text-xs font-semibold text-muted-foreground uppercase">
                    <ColumnHeaderTip
                      label="Residual (Net)"
                      tip="Net risk score after controls — residual likelihood × impact."
                    />
                  </th>
                  <th className="px-4 py-3 text-center text-xs font-semibold text-muted-foreground uppercase">
                    <ColumnHeaderTip
                      label="Level"
                      tip="Banded residual score: Low ≤4, Medium 5–9, High 10–16, Critical ≥17."
                    />
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground uppercase">
                    <ColumnHeaderTip
                      label="Treatment"
                      tip="Selected response strategy: Treat, Tolerate, Transfer, or Terminate."
                    />
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground uppercase">
                    <ColumnHeaderTip
                      label="Owner"
                      tip="Named person accountable for managing and reviewing this risk."
                    />
                  </th>
                  <th className="px-4 py-3 text-center text-xs font-semibold text-muted-foreground uppercase">
                    <ColumnHeaderTip
                      label="Actions"
                      tip={
                        registerMode === 'import_triage'
                          ? 'Accept into the live register or reject the import suggestion.'
                          : 'Open the Risk Profile page (view or edit).'
                      }
                    />
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {visibleRisks.length === 0 && (
                  <tr>
                    <td
                      colSpan={9}
                      className="text-center py-12 text-muted-foreground"
                      data-testid={
                        loadError ? 'risk-register-unavailable' : 'risk-register-empty'
                      }
                    >
                      {loadError
                        ? 'Risk register unavailable — not an empty register.'
                        : registerMode === 'import_triage'
                          ? 'No import-sourced risks awaiting triage.'
                          : auditOnly || auditRefFilter || nearMissRefFilter
                            ? 'No risks match the current filters.'
                            : 'No risks found in the register'}
                    </td>
                  </tr>
                )}
                {visibleRisks.map((risk) => (
                  <tr
                    key={risk.id}
                    className="hover:bg-muted/30 transition-colors cursor-pointer"
                    role="button"
                    tabIndex={0}
                    aria-label={`Open profile for ${risk.reference}`}
                    data-testid={`risk-row-${risk.id}`}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault()
                        openRiskProfile(risk.id)
                      }
                    }}
                    onClick={() => openRiskProfile(risk.id)}
                  >
                    <td className="px-4 py-4">
                      <span className="font-mono text-primary underline-offset-2 hover:underline">
                        {risk.reference}
                      </span>
                    </td>
                    <td className="px-4 py-4">
                      <div className="flex items-center gap-2">
                        {!risk.is_within_appetite && (
                          <span
                            className="w-2 h-2 bg-destructive rounded-full animate-pulse"
                            title="Outside Risk Appetite"
                          ></span>
                        )}
                        <span className="text-foreground">{risk.title}</span>
                      </div>
                      {(risk.is_escalated || (risk.linked_audits?.length ?? 0) > 0 || (risk.linked_actions?.length ?? 0) > 0) && (
                        <div className="mt-2 flex flex-wrap gap-2">
                          {risk.is_escalated && (
                            <Badge variant="destructive" className="text-[10px] uppercase">
                              Escalated
                            </Badge>
                          )}
                          {risk.linked_audits?.map((reference) => {
                            const target = linkedAuditTargets[normalizeLinkedReference(reference)]
                            if (!target) {
                              return (
                                <Badge
                                  key={reference}
                                  variant="outline"
                                  className="font-mono text-[10px]"
                                >
                                  {reference}
                                </Badge>
                              )
                            }
                            return (
                              <Link
                                key={reference}
                                to={target.path}
                                aria-label={`Open ${target.kind} ${reference}`}
                                className="inline-flex items-center rounded-full border border-border px-2 py-0.5 font-mono text-[10px] text-primary transition-colors hover:bg-muted hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                                onClick={(event) => event.stopPropagation()}
                              >
                                {reference}
                              </Link>
                            )
                          })}
                          {(risk.linked_actions?.length ?? 0) > 0 && (
                            <>
                              {risk.linked_actions?.map((actionRef) => (
                                <Badge
                                  key={actionRef}
                                  variant="outline"
                                  className="font-mono text-[10px]"
                                  data-testid={`risk-linked-action-${actionRef}`}
                                >
                                  {actionRef}
                                </Badge>
                              ))}
                              <Link
                                to={`/actions?sourceType=risk&sourceId=${risk.id}`}
                                aria-label={`Open CAPA for ${risk.reference}`}
                                data-testid={`risk-open-capa-${risk.id}`}
                                className="inline-flex items-center rounded-full border border-border px-2 py-0.5 text-[10px] text-primary transition-colors hover:bg-muted hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                                onClick={(event) => event.stopPropagation()}
                              >
                                Open CAPA
                              </Link>
                            </>
                          )}
                        </div>
                      )}
                    </td>
                    <td className="px-4 py-4">
                      <Badge variant="default">
                        {CATEGORIES.find((c) => c.id === risk.category)?.label || risk.category}
                      </Badge>
                    </td>
                    <td className="px-4 py-4 text-center">
                      <span
                        className="text-xl font-bold text-muted-foreground"
                        title="Inherent (gross) score"
                      >
                        {risk.inherent_score}
                      </span>
                    </td>
                    <td className="px-4 py-4 text-center">
                      <span
                        className="text-xl font-bold text-primary"
                        title="Residual (net) score"
                      >
                        {risk.residual_score}
                      </span>
                    </td>
                    <td className="px-4 py-4 text-center">{getRiskLevelBadge(risk.risk_level)}</td>
                    <td className="px-4 py-4">{getTreatmentBadge(risk.treatment_strategy)}</td>
                    <td className="px-4 py-4">
                      <button
                        type="button"
                        className="flex items-center gap-2 rounded px-1 py-0.5 text-left hover:bg-muted"
                        data-testid={`risk-owner-edit-${risk.id}`}
                        aria-label={`Open profile to edit owner for ${risk.reference}`}
                        onClick={(e) => {
                          e.stopPropagation()
                          openRiskProfile(risk.id)
                        }}
                      >
                        <User className="h-4 w-4 shrink-0 text-muted-foreground" />
                        <span
                          className={cn(
                            'text-sm',
                            risk.risk_owner_name
                              ? 'text-foreground'
                              : 'italic text-muted-foreground',
                          )}
                        >
                          {risk.risk_owner_name || 'Unassigned'}
                        </span>
                      </button>
                    </td>
                    <td className="px-4 py-4 text-center">
                      {registerMode === 'import_triage' ? (
                        <div className="flex flex-col items-stretch justify-center gap-2 sm:flex-row sm:items-center">
                          <Button
                            variant="ghost"
                            size="sm"
                            aria-label={`Open ${risk.reference}`}
                            data-testid={`risk-open-${risk.id}`}
                            onClick={(e) => {
                              e.stopPropagation()
                              openRiskProfile(risk.id)
                            }}
                          >
                            <Eye className="h-4 w-4" />
                          </Button>
                          <Button
                            size="sm"
                            className="text-xs"
                            disabled={triageSubmitting}
                            data-testid={`risk-accept-${risk.id}`}
                            onClick={(e) => {
                              e.stopPropagation()
                              void resolveImportTriage(risk.id, 'accept')
                            }}
                          >
                            Accept
                          </Button>
                          <Button
                            size="sm"
                            variant="destructive"
                            className="text-xs"
                            disabled={triageSubmitting}
                            data-testid={`risk-reject-${risk.id}`}
                            onClick={(e) => {
                              e.stopPropagation()
                              openRejectDialog(risk.id)
                            }}
                          >
                            Reject
                          </Button>
                        </div>
                      ) : (
                        <div className="flex items-center justify-center gap-2">
                          <Button
                            variant="ghost"
                            size="sm"
                            aria-label={`Open ${risk.reference}`}
                            data-testid={`risk-open-${risk.id}`}
                            onClick={(e) => {
                              e.stopPropagation()
                              openRiskProfile(risk.id)
                            }}
                          >
                            <Eye className="h-4 w-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            aria-label={`Edit ${risk.reference} on profile`}
                            data-testid={`risk-edit-${risk.id}`}
                            onClick={(e) => {
                              e.stopPropagation()
                              openRiskProfile(risk.id)
                            }}
                          >
                            <Edit2 className="h-4 w-4" />
                          </Button>
                        </div>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {/* Heat Map View */}
      {view === 'heatmap' && heatmapUnavailable && (
        <Card>
          <CardContent className="p-6" data-testid="risk-heatmap-unavailable">
            <h2 className="text-xl font-bold mb-2 text-foreground">Heat map unavailable</h2>
            <p className="text-muted-foreground">
              The residual risk heat map could not be loaded. This is not an empty matrix — retry
              when the API is available.
            </p>
            <Button className="mt-4" variant="secondary" onClick={() => void loadRisks()}>
              Retry
            </Button>
          </CardContent>
        </Card>
      )}

      {view === 'heatmap' && heatMapData && !heatmapUnavailable && (
        <Card>
          <CardContent className="p-6">
            <RiskHeatMap
              data={heatMapData}
              scoreType={scoreType}
              focusMode={focusMode}
              selectedCell={cellFilter}
              riskDetails={heatmapRiskDetails}
              onScoreTypeChange={setScoreType}
              onFocusModeChange={setFocusMode}
              auditFilterActive={auditOnly || Boolean(auditRefFilter)}
              trends={trends}
              topMovers={topMovers}
              onOpenRisk={(id) => {
                navigate(`/risk-register/${id}`)
              }}
              onCellSelect={(cell) => {
                if (cell.risk_count === 0) return
                setCellFilter((prev) =>
                  prev?.likelihood === cell.likelihood && prev?.impact === cell.impact
                    ? null
                    : { likelihood: cell.likelihood, impact: cell.impact },
                )
              }}
              onShowInRegister={(cell) => {
                setCellFilter({ likelihood: cell.likelihood, impact: cell.impact })
                setView('register')
              }}
              onClearCellFilter={() => {
                setCellFilter(null)
              }}
            />
          </CardContent>
        </Card>
      )}

      {/* Bow-Tie View */}
      {bowtieEnabled && view === 'bowtie' && (
        <Card>
          <CardContent className="p-6">
            <h2 className="text-xl font-bold mb-6 text-foreground">Bow-Tie Analysis</h2>
            <div className="text-center py-12 text-muted-foreground">
              <GitBranch className="w-16 h-16 mx-auto mb-4 opacity-50" />
              <p>Bow-tie analysis is not available yet</p>
              <p className="text-sm mt-2">
                Open a risk from the register to use its full Risk Profile. Structured causes,
                consequences, and controls will appear here when this feature is ready.
              </p>
              <Button onClick={() => setView('register')} className="mt-4">
                Back to Risk Register
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      <Dialog
        open={detailMode === 'create'}
        onOpenChange={(open) => {
          if (!open) closeCreateDialog()
        }}
      >
        <DialogContent className="sm:max-w-lg" data-testid="risk-create-dialog">
          <DialogHeader>
            <DialogTitle>Add risk</DialogTitle>
            <DialogDescription>
              Create a register entry. After create you open the full Risk Profile. Inherent is the
              gross score before controls; residual is the net score after controls.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-3">
            <div className="space-y-1.5">
              <Label htmlFor="risk-detail-title">Title</Label>
              <Input
                id="risk-detail-title"
                value={titleDraft}
                onChange={(e) => setTitleDraft(e.target.value)}
                disabled={detailSaving}
                data-testid="risk-detail-title"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="risk-detail-description">Description</Label>
              <textarea
                id="risk-detail-description"
                value={descriptionDraft}
                onChange={(e) => setDescriptionDraft(e.target.value)}
                rows={3}
                disabled={detailSaving}
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                data-testid="risk-detail-description"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="risk-detail-owner">Owner name</Label>
              <Input
                id="risk-detail-owner"
                value={ownerDraft}
                onChange={(e) => setOwnerDraft(e.target.value)}
                placeholder="e.g. Jane Smith"
                disabled={detailSaving}
                data-testid="risk-detail-owner"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="risk-detail-category">Category</Label>
              <select
                id="risk-detail-category"
                value={categoryDraft}
                onChange={(e) => setCategoryDraft(e.target.value)}
                disabled={detailSaving}
                className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm"
                data-testid="risk-detail-category"
              >
                {CATEGORIES.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.label}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <DialogFooter className="gap-2 sm:gap-0">
            <Button type="button" variant="secondary" onClick={closeCreateDialog} disabled={detailSaving}>
              Cancel
            </Button>
            <Button
              type="button"
              onClick={() => void saveCreateRisk()}
              disabled={detailSaving}
              data-testid="risk-detail-save"
            >
              {detailSaving ? 'Saving…' : 'Create risk'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog
        open={rejectDialogOpen}
        onOpenChange={(open) => {
          if (!open && !triageSubmitting) closeRejectDialog()
        }}
      >
        <DialogContent
          className="sm:max-w-md"
          onEscapeKeyDown={(e) => triageSubmitting && e.preventDefault()}
          onPointerDownOutside={(e) => triageSubmitting && e.preventDefault()}
        >
          <DialogHeader>
            <DialogTitle>Reject import suggestion</DialogTitle>
            <DialogDescription>
              This closes the risk as rejected (auditable). Add an optional note for the escalation record—recommended
              for audit trail.
            </DialogDescription>
          </DialogHeader>
          <label htmlFor="import-triage-reject-notes" className="text-sm font-medium text-foreground">
            Notes
          </label>
          <textarea
            id="import-triage-reject-notes"
            value={rejectNotes}
            onChange={(e) => setRejectNotes(e.target.value)}
            maxLength={2000}
            rows={4}
            placeholder="Reason or context (optional, max 2000 characters)"
            className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            disabled={triageSubmitting}
          />
          <DialogFooter className="gap-2 sm:gap-0">
            <Button type="button" variant="secondary" onClick={closeRejectDialog} disabled={triageSubmitting}>
              Cancel
            </Button>
            <Button
              type="button"
              variant="destructive"
              onClick={() => void confirmRejectWithNotes()}
              disabled={triageSubmitting}
            >
              {triageSubmitting ? 'Rejecting…' : 'Confirm reject'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog
        open={importDialogOpen}
        onOpenChange={(open) => {
          if (!open && !importBusy) resetImportDialog()
        }}
      >
        <DialogContent
          className="sm:max-w-lg"
          data-testid="risk-import-dialog"
          onEscapeKeyDown={(e) => importBusy && e.preventDefault()}
          onPointerDownOutside={(e) => importBusy && e.preventDefault()}
        >
          <DialogHeader>
            <DialogTitle>{t('risk_register.excel_import.dialog_title')}</DialogTitle>
            <DialogDescription>{t('risk_register.excel_import.dialog_desc')}</DialogDescription>
          </DialogHeader>
          {importReport ? (
            <div className="space-y-3 text-sm">
              <p data-testid="risk-import-summary">
                {t('risk_register.excel_import.summary', {
                  total: importReport.total_rows,
                  creates: importReport.creates,
                  updates: importReport.updates,
                  errors: importReport.error_rows,
                })}
              </p>
              {importReport.action_plan_skipped ? (
                <p className="text-muted-foreground">{t('risk_register.excel_import.action_plan_skipped')}</p>
              ) : null}
              {importReport.errors.length > 0 ? (
                <ul
                  className="max-h-40 overflow-y-auto rounded-md border border-destructive/30 bg-destructive/5 p-3 text-destructive"
                  data-testid="risk-import-errors"
                >
                  {importReport.errors.slice(0, 20).map((err) => (
                    <li key={`${err.row}-${err.code}`}>
                      Row {err.row}: {err.message}
                    </li>
                  ))}
                </ul>
              ) : null}
              {importReport.preview.length > 0 ? (
                <ul className="max-h-40 overflow-y-auto rounded-md border border-input p-3" data-testid="risk-import-preview">
                  {importReport.preview.slice(0, 10).map((row) => (
                    <li key={`${row.row}-${row.reference}`}>
                      {row.action === 'create' ? '+' : '~'} {row.reference} — {row.title}
                    </li>
                  ))}
                </ul>
              ) : null}
            </div>
          ) : null}
          <DialogFooter className="gap-2 sm:gap-0">
            <Button type="button" variant="secondary" onClick={resetImportDialog} disabled={importBusy}>
              {t('risk_register.excel_import.cancel')}
            </Button>
            <Button
              type="button"
              onClick={() => void commitExcelImport()}
              disabled={importBusy || !importReport?.ok}
              data-testid="risk-import-commit"
            >
              {importBusy ? t('risk_register.excel_import.committing') : t('risk_register.excel_import.commit')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
