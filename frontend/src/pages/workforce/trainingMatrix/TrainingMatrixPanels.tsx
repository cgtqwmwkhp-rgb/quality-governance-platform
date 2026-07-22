import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import {
  ArrowDown,
  ArrowUp,
  ChevronDown,
  ChevronRight,
  Download,
  ExternalLink,
  Mail,
  Upload,
} from 'lucide-react'
import {
  getApiErrorMessage,
  trainingMatrixApi,
  workforceApi,
  type EngineerProfile,
  type TrainingMatrixComplianceRow,
  type TrainingMatrixFrequencyChangeRequest,
  type TrainingMatrixImport,
  type TrainingMatrixMatrixCell,
  type TrainingMatrixNameMapItem,
  type TrainingMatrixRequirement,
} from '../../../api/client'
import {
  ATLAS_HUB_URL,
  type TrainingMatrixPersonCompliance,
  type TrainingMatrixSummary,
} from '../../../api/trainingMatrixClient'
import { Badge, type BadgeVariant } from '../../../components/ui/Badge'
import { Button } from '../../../components/ui/Button'
import { Card, CardContent, CardHeader } from '../../../components/ui/Card'
import { Input } from '../../../components/ui/Input'
import { Switch } from '../../../components/ui/Switch'
import { cn } from '../../../helpers/utils'
import {
  Sheet,
  SheetBody,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '../../../components/ui/Sheet'
import { TableSkeleton } from '../../../components/ui/SkeletonLoader'
import { toast } from '../../../contexts/ToastContext'
import {
  BOARD_ROLES,
  type BoardRole,
  buildCourseMetricRollups,
  buildDepartmentMetricRollups,
  buildPersonRollups,
  buildStatusBriefings,
  computeModuleRoleStats,
  computePeopleFullyOkStats,
  EMPTY_ENTITY_METRIC_FILTERS,
  EMPTY_PERSON_ROLLUP_FILTERS,
  type EntityMetricColumnFilters,
  type EntityMetricRollup,
  type EntityMetricSortKey,
  entityMetricRollupsToCsv,
  filterEntityMetricRollups,
  filterPersonRollups,
  filterRowsByHorizon,
  type BoardHorizon,
  type Horizon,
  HORIZON_FILTERS,
  horizonFilterLabel,
  horizonForRow,
  computeHorizonCounts,
  isCoverageHorizon,
  isGapStatus,
  isOkStatus,
  isPlanningHorizon,
  moduleViewForRole,
  previewNotifyRecipients,
  myTrainingSummary,
  type PersonRollupColumnFilters,
  type PersonRollupSortKey,
  personRollupsToCsv,
  resolveBoardRole,
  rowsToCsv,
  type SortDirection,
  sortEntityMetricRollups,
  sortPersonRollups,
  statusLabel,
  topCoursesInHorizon,
} from './trainingMatrixBoardHelpers'
import { ComplianceBarChart, DueForwardBars, StatusPieChart } from './trainingMatrixCharts'

const PERSON_ROLLUP_COLUMNS: { key: PersonRollupSortKey; label: string; filterPlaceholder: string }[] =
  [
    { key: 'person', label: 'Person', filterPlaceholder: 'Filter name' },
    { key: 'department', label: 'Department', filterPlaceholder: 'Filter dept' },
    { key: 'complete', label: 'Complete', filterPlaceholder: '=' },
    { key: 'overdue', label: 'Overdue', filterPlaceholder: '=' },
    { key: 'pct', label: '%', filterPlaceholder: '=' },
    { key: 'need', label: 'Need to complete', filterPlaceholder: '=' },
  ]

function entityMetricColumns(nameLabel: string): {
  key: EntityMetricSortKey
  label: string
  filterPlaceholder: string
}[] {
  return [
    { key: 'label', label: nameLabel, filterPlaceholder: 'Filter' },
    { key: 'complete', label: 'Complete', filterPlaceholder: '=' },
    { key: 'overdue', label: 'Overdue', filterPlaceholder: '=' },
    { key: 'pct', label: '%', filterPlaceholder: '=' },
    { key: 'need', label: 'Need to complete', filterPlaceholder: '=' },
  ]
}

type EntityDrilldown = {
  title: string
  subtitle?: string
  rollup: EntityMetricRollup
}

type RoleScope = BoardRole | 'Overall'

const HORIZON_VARIANT: Record<Horizon, BadgeVariant> = {
  overdue: 'destructive',
  d30: 'warning',
  d60: 'warning',
  d180: 'info',
  ok: 'success',
}

const BRIEFING_ROTATE_MS = 8000

function formatImportStamp(imp: TrainingMatrixImport): string {
  const when = imp.created_at
    ? new Date(imp.created_at).toLocaleString(undefined, {
        day: '2-digit',
        month: 'short',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      })
    : 'unknown time'
  const who = imp.uploaded_by_name?.trim() || imp.uploaded_by_email?.trim() || 'unknown user'
  return `${when} · ${who} · ${imp.filename}`
}

function AdminSection({
  title,
  subtitle,
  open,
  onToggle,
  testId,
  children,
  headerRight,
}: {
  title: string
  subtitle?: string
  open: boolean
  onToggle: () => void
  testId: string
  children: ReactNode
  headerRight?: ReactNode
}) {
  return (
    <Card data-testid={testId}>
      <CardHeader className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <button
          type="button"
          className="flex flex-1 items-start gap-2 text-left"
          onClick={onToggle}
          aria-expanded={open}
          data-testid={`${testId}-toggle`}
        >
          <ChevronDown
            className={`mt-0.5 h-4 w-4 shrink-0 text-muted-foreground transition-transform ${
              open ? '' : '-rotate-90'
            }`}
          />
          <div>
            <p className="font-medium">{title}</p>
            {subtitle ? <p className="text-sm text-muted-foreground">{subtitle}</p> : null}
          </div>
        </button>
        {headerRight}
      </CardHeader>
      {open ? <CardContent className="space-y-3">{children}</CardContent> : null}
    </Card>
  )
}

function AtlasCta({ url = ATLAS_HUB_URL }: { url?: string }) {
  const { t } = useTranslation()
  return (
    <a
      href={url}
      target="_blank"
      rel="noreferrer"
      className="inline-flex items-center gap-1.5 text-sm text-primary hover:underline"
      data-testid="training-matrix-atlas-link"
    >
      {t('workforce.training_matrix.open_atlas', 'Complete in Atlas')}
      <ExternalLink className="w-3.5 h-3.5" />
    </a>
  )
}

function HorizonBadge({ row }: { row: TrainingMatrixComplianceRow }) {
  const horizon = horizonForRow(row.status, row.qgp_due_on)
  return <Badge variant={HORIZON_VARIANT[horizon]}>{statusLabel(row)}</Badge>
}

function downloadCsv(filename: string, csv: string) {
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

function ComplianceTable({ rows, loading }: { rows: TrainingMatrixComplianceRow[]; loading: boolean }) {
  const { t } = useTranslation()
  if (loading) return <TableSkeleton rows={6} columns={6} />
  if (rows.length === 0) {
    return (
      <p className="text-sm text-muted-foreground py-8 text-center" data-testid="training-matrix-empty">
        {t(
          'workforce.training_matrix.empty_compliance',
          'No compliance rows yet. Upload an Atlas matrix and configure role/department requirements.',
        )}
      </p>
    )
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border text-left text-muted-foreground">
            <th className="py-2 px-3">Person</th>
            <th className="py-2 px-3">Course</th>
            <th className="py-2 px-3">Status</th>
            <th className="py-2 px-3">Passed</th>
            <th className="py-2 px-3">QGP due</th>
            <th className="py-2 px-3">Atlas expiry</th>
            <th className="py-2 px-3" />
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={`${row.atlas_name}-${row.course_key}`} className="border-b border-border/50">
              <td className="py-2 px-3">
                <div className="font-medium">{row.engineer_display_name || row.atlas_name}</div>
                <div className="text-xs text-muted-foreground">{row.department || '—'}</div>
              </td>
              <td className="py-2 px-3">
                {row.course_display_name}
                <div className="text-xs text-muted-foreground">{row.frequency_years}y cycle</div>
              </td>
              <td className="py-2 px-3">
                <HorizonBadge row={row} />
              </td>
              <td className="py-2 px-3 text-muted-foreground">{row.passed_on || '—'}</td>
              <td className="py-2 px-3 text-muted-foreground">{row.qgp_due_on || '—'}</td>
              <td className="py-2 px-3 text-muted-foreground">{row.expires_on || '—'}</td>
              <td className="py-2 px-3">
                {row.status === 'compliant' ? null : <AtlasCta url={row.atlas_hub_url || ATLAS_HUB_URL} />}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

type ViewId = 'group' | 'course' | 'individual' | 'module' | 'analytics'

const VIEWS: { id: ViewId; label: string }[] = [
  { id: 'individual', label: 'By individual' },
  { id: 'group', label: 'By group' },
  { id: 'course', label: 'By course' },
  { id: 'module', label: 'By module' },
  { id: 'analytics', label: 'Analytics' },
]

export function TrainingMatrixGapBoard() {
  const { t } = useTranslation()
  const [rows, setRows] = useState<TrainingMatrixComplianceRow[]>([])
  const [summary, setSummary] = useState<TrainingMatrixSummary | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [horizon, setHorizon] = useState<BoardHorizon>('overdue')
  const [view, setView] = useState<ViewId>('individual')
  const [roleScope, setRoleScope] = useState<RoleScope>('Overall')
  const [briefingIndex, setBriefingIndex] = useState(0)
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [notifying, setNotifying] = useState(false)
  const [latestImport, setLatestImport] = useState<TrainingMatrixImport | null>(null)
  const [drawerPersonId, setDrawerPersonId] = useState<number | null>(null)
  const [personDetail, setPersonDetail] = useState<TrainingMatrixPersonCompliance | null>(null)
  const [personLoading, setPersonLoading] = useState(false)
  const [personSortKey, setPersonSortKey] = useState<PersonRollupSortKey>('overdue')
  const [personSortDir, setPersonSortDir] = useState<SortDirection>('desc')
  const [personFilters, setPersonFilters] =
    useState<PersonRollupColumnFilters>(EMPTY_PERSON_ROLLUP_FILTERS)
  const [entitySortKey, setEntitySortKey] = useState<EntityMetricSortKey>('overdue')
  const [entitySortDir, setEntitySortDir] = useState<SortDirection>('desc')
  const [entityFilters, setEntityFilters] =
    useState<EntityMetricColumnFilters>(EMPTY_ENTITY_METRIC_FILTERS)
  const [entityDrilldown, setEntityDrilldown] = useState<EntityDrilldown | null>(null)

  useEffect(() => {
    setLoading(true)
    setError(null)
    Promise.allSettled([
      trainingMatrixApi.listCompliance(),
      trainingMatrixApi.getSummary(),
      trainingMatrixApi.getLatestImport(),
    ])
      .then(([complianceResult, summaryResult, latestImportResult]) => {
        if (complianceResult.status === 'fulfilled') {
          setRows(complianceResult.value.items || [])
          setSummary(summaryResult.status === 'fulfilled' ? summaryResult.value : null)
        } else {
          setRows([])
          setSummary(null)
          setError(getApiErrorMessage(complianceResult.reason))
        }
        setLatestImport(
          latestImportResult.status === 'fulfilled' ? latestImportResult.value : null,
        )
      })
      .finally(() => setLoading(false))
  }, [])

  const scopedRows = useMemo(() => {
    if (roleScope === 'Overall') return rows
    return rows.filter((r) => resolveBoardRole(r.department, r.board_role_override) === roleScope)
  }, [rows, roleScope])

  // Hero always shows all roles from summary (full workforce); fallback computes from all rows.
  const heroModuleStats = useMemo(
    () => summary?.module_ok ?? computeModuleRoleStats(rows),
    [summary, rows],
  )
  const peopleStats = useMemo(() => {
    if (summary?.people_fully_ok?.length) {
      return summary.people_fully_ok.map((s) => ({
        role: s.role,
        ok: s.ok,
        total: s.total,
        pct: s.pct,
        metric: 'people_fully_ok' as const,
      }))
    }
    return computePeopleFullyOkStats(rows)
  }, [summary, rows])
  const briefingRoleStats = useMemo(
    () => (roleScope === 'Overall' ? peopleStats : computePeopleFullyOkStats(scopedRows)),
    [peopleStats, roleScope, scopedRows],
  )
  const briefings = useMemo(
    () => buildStatusBriefings(scopedRows, briefingRoleStats),
    [scopedRows, briefingRoleStats],
  )

  useEffect(() => {
    if (briefings.length <= 1) return
    const id = window.setInterval(() => {
      setBriefingIndex((i) => (i + 1) % briefings.length)
    }, BRIEFING_ROTATE_MS)
    return () => window.clearInterval(id)
  }, [briefings.length])

  useEffect(() => {
    setBriefingIndex(0)
  }, [briefings.length])

  const filteredRows = useMemo(
    () => filterRowsByHorizon(scopedRows, horizon),
    [scopedRows, horizon],
  )

  const coverageMode = isCoverageHorizon(horizon)

  useEffect(() => {
    if (coverageMode) {
      setPersonSortKey('pct')
      setPersonSortDir('asc')
      setEntitySortKey('pct')
      setEntitySortDir('asc')
      return
    }
    setPersonSortKey('overdue')
    setPersonSortDir('desc')
    setEntitySortKey(view === 'module' ? 'pct' : 'overdue')
    setEntitySortDir(view === 'module' ? 'asc' : 'desc')
  }, [coverageMode, view])

  const topCourses = useMemo(() => {
    if (coverageMode) return []
    if (horizon === 'all') {
      const counts = new Map<string, number>()
      for (const row of filteredRows) counts.set(row.course_display_name, (counts.get(row.course_display_name) || 0) + 1)
      return [...counts.entries()]
        .map(([course_display_name, count]) => ({ course_display_name, count }))
        .sort((a, b) => b.count - a.count)
        .slice(0, 5)
    }
    return topCoursesInHorizon(scopedRows, horizon as Horizon, 5)
  }, [scopedRows, filteredRows, horizon, coverageMode])

  const groupRollups = useMemo(
    () => buildDepartmentMetricRollups(scopedRows, filteredRows),
    [scopedRows, filteredRows],
  )
  const courseRollups = useMemo(
    () => buildCourseMetricRollups(scopedRows, filteredRows),
    [scopedRows, filteredRows],
  )
  const personRollups = useMemo(
    () => buildPersonRollups(scopedRows, filteredRows),
    [scopedRows, filteredRows],
  )
  const displayedPersonRollups = useMemo(
    () => sortPersonRollups(filterPersonRollups(personRollups, personFilters), personSortKey, personSortDir),
    [personRollups, personFilters, personSortKey, personSortDir],
  )
  const moduleRole: BoardRole = roleScope === 'Overall' ? 'Engineer' : roleScope
  const moduleRollups = useMemo(
    () => moduleViewForRole(rows, moduleRole, new Date(), filteredRows),
    [rows, moduleRole, filteredRows],
  )

  const activeEntityRollups = useMemo(() => {
    if (view === 'group') return groupRollups
    if (view === 'course') return courseRollups
    if (view === 'module') return moduleRollups
    return []
  }, [view, groupRollups, courseRollups, moduleRollups])

  const displayedEntityRollups = useMemo(
    () =>
      sortEntityMetricRollups(
        filterEntityMetricRollups(activeEntityRollups, entityFilters),
        entitySortKey,
        entitySortDir,
      ),
    [activeEntityRollups, entityFilters, entitySortKey, entitySortDir],
  )

  const tableScopeChip = useMemo(() => {
    if (view === 'individual') {
      const count = displayedPersonRollups.length
      return { count, unit: count === 1 ? 'person' : 'people' }
    }
    if (view === 'group' || view === 'course' || view === 'module') {
      const count = displayedEntityRollups.length
      return { count, unit: count === 1 ? 'row' : 'rows' }
    }
    const count = scopedRows.length
    return { count, unit: count === 1 ? 'module' : 'modules' }
  }, [view, displayedPersonRollups, displayedEntityRollups, scopedRows.length])

  useEffect(() => {
    setEntityFilters(EMPTY_ENTITY_METRIC_FILTERS)
    setEntityDrilldown(null)
  }, [view])

  const handlePersonSort = (key: PersonRollupSortKey) => {
    if (personSortKey === key) {
      setPersonSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
      return
    }
    setPersonSortKey(key)
    setPersonSortDir(key === 'person' || key === 'department' ? 'asc' : 'desc')
  }

  const setPersonFilter = (key: keyof PersonRollupColumnFilters, value: string) => {
    setPersonFilters((prev) => ({ ...prev, [key]: value }))
  }

  const handleEntitySort = (key: EntityMetricSortKey) => {
    if (entitySortKey === key) {
      setEntitySortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
      return
    }
    setEntitySortKey(key)
    setEntitySortDir(key === 'label' ? 'asc' : key === 'pct' && view === 'module' ? 'asc' : 'desc')
  }

  const setEntityFilter = (key: keyof EntityMetricColumnFilters, value: string) => {
    setEntityFilters((prev) => ({ ...prev, [key]: value }))
  }

  const openEntityDrilldown = (rollup: EntityMetricRollup, nameLabel: string) => {
    setEntityDrilldown({
      title: rollup.label,
      subtitle: `${nameLabel} · ${rollup.complete}/${rollup.total} complete · ${rollup.overdue} overdue`,
      rollup,
    })
  }

  const renderEntityMetricTable = (nameLabel: string, testId: string) => {
    const columns = entityMetricColumns(nameLabel)
    return (
      <div className="overflow-x-auto">
        <table className="w-full text-sm" data-testid={testId}>
          <thead>
            <tr className="border-b border-border text-left text-muted-foreground">
              {columns.map(({ key, label }) => {
                const active = entitySortKey === key
                return (
                  <th
                    key={key}
                    className="py-2 px-3 font-medium"
                    scope="col"
                    aria-sort={
                      active ? (entitySortDir === 'asc' ? 'ascending' : 'descending') : 'none'
                    }
                  >
                    <button
                      type="button"
                      className={cn(
                        'inline-flex items-center gap-1 rounded-sm hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                        active ? 'text-foreground' : 'text-muted-foreground',
                      )}
                      onClick={() => handleEntitySort(key)}
                      data-testid={`${testId}-sort-${key}`}
                    >
                      {label}
                      {active ? (
                        entitySortDir === 'asc' ? (
                          <ArrowUp className="w-3.5 h-3.5" aria-hidden="true" />
                        ) : (
                          <ArrowDown className="w-3.5 h-3.5" aria-hidden="true" />
                        )
                      ) : null}
                    </button>
                  </th>
                )
              })}
            </tr>
            <tr className="border-b border-border bg-muted/20" data-testid={`${testId}-filters`}>
              {columns.map(({ key, filterPlaceholder }) => (
                <th key={`filter-${key}`} className="py-1.5 px-2 font-normal">
                  <Input
                    value={entityFilters[key]}
                    onChange={(e) => setEntityFilter(key, e.target.value)}
                    placeholder={filterPlaceholder}
                    aria-label={`Filter ${key}`}
                    data-testid={`${testId}-filter-${key}`}
                    className="h-8 text-xs"
                  />
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {displayedEntityRollups.map((r) => (
              <tr
                key={r.key}
                className="border-b border-border/50 hover:bg-muted/40 cursor-pointer"
                onClick={() => openEntityDrilldown(r, nameLabel)}
              >
                <td className="py-2 px-3 font-medium text-primary underline-offset-2 hover:underline">
                  {r.label}
                </td>
                <td className="py-2 px-3">{r.complete}</td>
                <td className="py-2 px-3">
                  <Badge variant={r.overdue > 0 ? 'destructive' : 'success'}>{r.overdue}</Badge>
                </td>
                <td className="py-2 px-3 font-medium">{r.pct}%</td>
                <td className="py-2 px-3 text-muted-foreground">{r.need}</td>
              </tr>
            ))}
            {displayedEntityRollups.length === 0 ? (
              <tr>
                <td colSpan={5} className="py-6 text-center text-muted-foreground">
                  {view === 'module'
                    ? `No required modules mapped to ${moduleRole} yet.`
                    : roleScope !== 'Overall' && scopedRows.length === 0
                      ? 'No matrix requirements for this group — check Admin Training group mapping and frequency matrix.'
                      : 'No rows in this filter.'}
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    )
  }

  useEffect(() => {
    if (drawerPersonId == null) {
      setPersonDetail(null)
      return
    }
    setPersonLoading(true)
    trainingMatrixApi
      .getPersonCompliance(drawerPersonId)
      .then(setPersonDetail)
      .catch((err) => {
        setPersonDetail(null)
        toast.error(getApiErrorMessage(err, 'Could not load person training detail.'))
        setDrawerPersonId(null)
      })
      .finally(() => setPersonLoading(false))
  }, [drawerPersonId])

  const analyticsBars = useMemo(() => {
    const stats = summary?.module_ok ?? computeModuleRoleStats(rows)
    return stats
      .filter((s) => s.role !== 'Overall')
      .filter((s) => roleScope === 'Overall' || s.role === roleScope)
      .map((s) => ({
        label: s.role,
        okPct: s.pct,
        gapPct: s.total ? 100 - s.pct : 0,
      }))
  }, [summary, rows, roleScope])

  const analyticsPie = useMemo(() => {
    let ok = 0
    let dueSoon = 0
    let gap = 0
    for (const r of scopedRows) {
      if (r.status === 'due_soon') dueSoon += 1
      else if (isOkStatus(r.status)) ok += 1
      else if (isGapStatus(r.status)) gap += 1
    }
    return [
      { label: 'OK', value: ok, color: '#059669' },
      { label: 'Due soon', value: dueSoon, color: '#d97706' },
      { label: 'Needs action', value: gap, color: '#e11d48' },
    ]
  }, [scopedRows])

  const scopedHorizonCounts = useMemo(() => computeHorizonCounts(scopedRows), [scopedRows])

  const toggleSelected = (atlasName: string) => {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(atlasName)) next.delete(atlasName)
      else next.add(atlasName)
      return next
    })
  }

  const runNotify = (atlasNames: string[]) => {
    if (atlasNames.length === 0) return
    const { willEmail, willSkip } = previewNotifyRecipients(atlasNames, scopedRows)
    if (willEmail.length === 0) {
      toast.error(
        `No emailable gaps in this selection (${willSkip.length} would be skipped — notify only sends for overdue/missing/pending/failed modules).`,
      )
      return
    }
    const confirmed = window.confirm(
      `Will email ${willEmail.length} · skip ${willSkip.length} (no gap-status modules).\n\n` +
        'Notify only emails people with overdue/missing/pending/failed training. Continue?',
    )
    if (!confirmed) return
    setNotifying(true)
    setError(null)
    void trainingMatrixApi
      .notify(willEmail)
      .then((res) => {
        toast.success(`Emailed ${res.sent} · skipped ${res.skipped} · failed ${res.failed}`)
        setSelected(new Set())
      })
      .catch((err) => setError(getApiErrorMessage(err, 'Could not send training emails.')))
      .finally(() => setNotifying(false))
  }

  const onExportCsv = () => {
    if (view === 'individual') {
      const csv = personRollupsToCsv(displayedPersonRollups)
      downloadCsv(`training-matrix-people-${horizon}-${new Date().toISOString().slice(0, 10)}.csv`, csv)
      toast.success(`Exported ${displayedPersonRollups.length} people`)
      return
    }
    if (view === 'group' || view === 'course' || view === 'module') {
      const labelHeader = view === 'group' ? 'Group' : view === 'course' ? 'Course' : 'Module'
      const csv = entityMetricRollupsToCsv(displayedEntityRollups, labelHeader)
      downloadCsv(
        `training-matrix-${view}-${horizon}-${new Date().toISOString().slice(0, 10)}.csv`,
        csv,
      )
      toast.success(`Exported ${displayedEntityRollups.length} ${view} rows`)
      return
    }
    const csv = rowsToCsv(filteredRows)
    downloadCsv(`training-matrix-${horizon}-${new Date().toISOString().slice(0, 10)}.csv`, csv)
    toast.success(`Exported ${filteredRows.length} row${filteredRows.length === 1 ? '' : 's'}`)
  }

  return (
    <div className="space-y-4" data-testid="training-matrix-gap-board">
      <Card>
        <CardHeader className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <div>
            <p className="font-medium">{t('workforce.training_matrix.gap_title', 'Training matrix board')}</p>
            <p className="text-sm text-muted-foreground">
              {t(
                'workforce.training_matrix.gap_subtitle',
                'Due dates use Atlas Passed + your frequency rules. Complete training in Atlas.',
              )}
            </p>
            {latestImport ? (
              <p className="text-xs text-muted-foreground mt-1" data-testid="training-matrix-last-upload">
                Atlas data on file: {formatImportStamp(latestImport)}
              </p>
            ) : (
              <p className="text-xs text-muted-foreground mt-1" data-testid="training-matrix-last-upload">
                No Atlas matrix uploaded yet — use Admin → Upload CSV.
              </p>
            )}
          </div>
          <AtlasCta />
        </CardHeader>
        <CardContent className="space-y-4">
          {error ? (
            <div className="mb-2 p-3 rounded-lg bg-destructive/10 text-destructive text-sm">{error}</div>
          ) : null}

          {briefings.length > 0 ? (
            <div
              className="flex items-start justify-between gap-3 p-3 rounded-lg bg-muted/50"
              data-testid="training-matrix-briefing"
            >
              <div>
                <p className="text-sm font-medium">{briefings[briefingIndex % briefings.length].title}</p>
                <p className="text-sm text-muted-foreground">
                  {briefings[briefingIndex % briefings.length].detail}
                </p>
              </div>
              {briefings.length > 1 ? (
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  data-testid="training-matrix-briefing-next"
                  onClick={() => setBriefingIndex((i) => (i + 1) % briefings.length)}
                >
                  Next
                  <ChevronRight className="w-3.5 h-3.5" />
                </Button>
              ) : null}
            </div>
          ) : null}

          <div className="space-y-2" data-testid="training-matrix-role-bar">
            <p className="text-xs text-muted-foreground">
              Module compliance (in-cycle) from the Training Matrix — blank frequency cells are excluded.
              Click a group to filter the board.
            </p>
            <div className="grid grid-cols-2 sm:grid-cols-5 gap-2">
              {heroModuleStats.map((stat) => {
                const people = peopleStats.find((p) => p.role === stat.role)
                const active = roleScope === stat.role
                return (
                  <button
                    key={stat.role}
                    type="button"
                    data-testid={`training-matrix-hero-${stat.role}`}
                    className={`p-2.5 rounded-lg border text-left transition-colors ${
                      active
                        ? 'border-primary bg-primary/10 ring-1 ring-primary'
                        : 'border-border hover:border-primary/50'
                    }`}
                    onClick={() => setRoleScope(stat.role as RoleScope)}
                  >
                    <p className="text-xs text-muted-foreground">{stat.role}</p>
                    <p className="text-lg font-semibold">{stat.pct}%</p>
                    <p className="text-xs text-muted-foreground">
                      {stat.ok}/{stat.total} modules OK
                      {stat.total === 0 ? ' — no matrix rules for this group' : ''}
                    </p>
                    {people && people.total > 0 ? (
                      <p className="text-[11px] text-muted-foreground mt-0.5">
                        {people.ok}/{people.total} people fully OK
                      </p>
                    ) : null}
                  </button>
                )
              })}
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2" role="tablist" aria-label="Horizon filter">
            {HORIZON_FILTERS.map((f) => (
              <button
                key={f.id}
                type="button"
                role="tab"
                aria-selected={horizon === f.id}
                data-testid={`training-matrix-horizon-${f.id}`}
                className={`px-3 py-1.5 text-sm rounded-full border ${
                  horizon === f.id
                    ? 'bg-primary text-primary-foreground border-primary'
                    : 'border-border text-muted-foreground hover:text-foreground'
                }`}
                onClick={() => setHorizon(f.id)}
              >
                {f.label}
              </button>
            ))}
          </div>

          {topCourses.length > 0 ? (
            <div className="text-sm">
              <p className="text-muted-foreground mb-1">Top courses in this horizon</p>
              <div className="flex flex-wrap gap-2">
                {topCourses.map((c) => (
                  <Badge key={c.course_display_name} variant="secondary">
                    {c.course_display_name} · {c.count}
                  </Badge>
                ))}
              </div>
            </div>
          ) : null}

          <div className="flex flex-wrap items-center justify-between gap-2 pt-2 border-t border-border">
            <div className="flex flex-wrap gap-1" role="tablist" aria-label="Board view">
              {VIEWS.map((v) => (
                <button
                  key={v.id}
                  type="button"
                  role="tab"
                  aria-selected={view === v.id}
                  data-testid={`training-matrix-view-${v.id}`}
                  className={`px-3 py-1.5 text-sm rounded-sm ${
                    view === v.id
                      ? 'bg-primary text-primary-foreground'
                      : 'text-muted-foreground hover:text-foreground'
                  }`}
                  onClick={() => setView(v.id)}
                >
                  {v.label}
                </button>
              ))}
            </div>
            <p
              className="w-full text-xs text-muted-foreground"
              data-testid="training-matrix-scope-chip"
            >
              Showing {tableScopeChip.count} {tableScopeChip.unit} · filter:{' '}
              {horizonFilterLabel(horizon)} · role: {roleScope}
              {coverageMode ? ' · coverage roster (includes 100% OK)' : ''}
            </p>
            <div className="flex items-center gap-2">
              <Button
                type="button"
                variant="outline"
                size="sm"
                disabled={selected.size === 0 || notifying}
                onClick={() => runNotify([...selected])}
                data-testid="training-matrix-email-selected"
              >
                <Mail className="w-3.5 h-3.5 mr-1.5" />
                Email selected ({selected.size})
              </Button>
              <Button
                type="button"
                variant="outline"
                size="sm"
                disabled={
                  (view === 'individual'
                    ? displayedPersonRollups.length === 0
                    : view === 'group' || view === 'course' || view === 'module'
                      ? displayedEntityRollups.length === 0
                      : filteredRows.length === 0) || notifying
                }
                onClick={() => {
                  if (view === 'individual') {
                    runNotify(displayedPersonRollups.map((p) => p.atlas_name))
                    return
                  }
                  if (view === 'group' || view === 'course' || view === 'module') {
                    // Coverage: membership rows may be full set; notify still gap-filters via preview.
                    runNotify([
                      ...new Set(
                        displayedEntityRollups.flatMap((r) =>
                          (coverageMode ? r.allRows : r.filteredRows).map((row) => row.atlas_name),
                        ),
                      ),
                    ])
                    return
                  }
                  runNotify([...new Set(filteredRows.map((r) => r.atlas_name))])
                }}
                data-testid="training-matrix-email-filter"
              >
                <Mail className="w-3.5 h-3.5 mr-1.5" />
                {coverageMode
                  ? 'Email gaps only'
                  : isPlanningHorizon(horizon)
                    ? 'Send reminders'
                    : 'Email everyone in filter'}
              </Button>
              <Button type="button" variant="outline" size="sm" onClick={onExportCsv} data-testid="training-matrix-export-csv">
                <Download className="w-3.5 h-3.5 mr-1.5" />
                Export CSV
              </Button>
            </div>
          </div>

          {loading ? (
            <TableSkeleton rows={6} columns={4} />
          ) : view === 'group' ? (
            renderEntityMetricTable('Group', 'training-matrix-group-table')
          ) : view === 'course' ? (
            renderEntityMetricTable('Course', 'training-matrix-course-table')
          ) : view === 'individual' ? (
            <div className="overflow-x-auto">
              <table className="w-full text-sm" data-testid="training-matrix-individual-table">
                <thead>
                  <tr className="border-b border-border text-left text-muted-foreground">
                    <th className="py-2 px-3" />
                    {PERSON_ROLLUP_COLUMNS.map(({ key, label }) => {
                      const active = personSortKey === key
                      return (
                        <th
                          key={key}
                          className="py-2 px-3 font-medium"
                          scope="col"
                          aria-sort={
                            active ? (personSortDir === 'asc' ? 'ascending' : 'descending') : 'none'
                          }
                        >
                          <button
                            type="button"
                            className={cn(
                              'inline-flex items-center gap-1 rounded-sm hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                              active ? 'text-foreground' : 'text-muted-foreground',
                            )}
                            onClick={() => handlePersonSort(key)}
                            data-testid={`training-matrix-individual-sort-${key}`}
                          >
                            {label}
                            {active ? (
                              personSortDir === 'asc' ? (
                                <ArrowUp className="w-3.5 h-3.5" aria-hidden="true" />
                              ) : (
                                <ArrowDown className="w-3.5 h-3.5" aria-hidden="true" />
                              )
                            ) : null}
                          </button>
                        </th>
                      )
                    })}
                  </tr>
                  <tr className="border-b border-border bg-muted/20" data-testid="training-matrix-individual-filters">
                    <th className="py-1.5 px-3" />
                    {PERSON_ROLLUP_COLUMNS.map(({ key, filterPlaceholder }) => (
                      <th key={`filter-${key}`} className="py-1.5 px-2 font-normal">
                        <Input
                          value={personFilters[key]}
                          onChange={(e) => setPersonFilter(key, e.target.value)}
                          placeholder={filterPlaceholder}
                          aria-label={`Filter ${key}`}
                          data-testid={`training-matrix-individual-filter-${key}`}
                          className="h-8 text-xs"
                        />
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {displayedPersonRollups.map((p) => (
                    <tr
                      key={p.atlas_name}
                      className="border-b border-border/50 hover:bg-muted/40 cursor-pointer"
                      onClick={() => p.person_id != null && setDrawerPersonId(p.person_id)}
                    >
                      <td className="py-2 px-3" onClick={(e) => e.stopPropagation()}>
                        <input
                          type="checkbox"
                          aria-label={`Select ${p.atlas_name}`}
                          checked={selected.has(p.atlas_name)}
                          onChange={() => toggleSelected(p.atlas_name)}
                        />
                      </td>
                      <td className="py-2 px-3 font-medium text-primary underline-offset-2 hover:underline">
                        {p.engineer_display_name || p.atlas_name}
                      </td>
                      <td className="py-2 px-3 text-muted-foreground">{p.department || '—'}</td>
                      <td className="py-2 px-3">{p.complete}</td>
                      <td className="py-2 px-3">
                        <Badge variant={p.overdue > 0 ? 'destructive' : 'success'}>{p.overdue}</Badge>
                      </td>
                      <td className="py-2 px-3 font-medium">{p.pct}%</td>
                      <td className="py-2 px-3 text-muted-foreground">{p.need}</td>
                    </tr>
                  ))}
                  {displayedPersonRollups.length === 0 ? (
                    <tr>
                      <td colSpan={7} className="py-6 text-center text-muted-foreground">
                        {roleScope !== 'Overall' && scopedRows.length === 0
                          ? 'No matrix requirements for this group — check Admin Training group mapping and frequency matrix.'
                          : 'No rows in this filter.'}
                      </td>
                    </tr>
                  ) : null}
                </tbody>
              </table>
            </div>
          ) : view === 'module' ? (
            <div className="space-y-2">
              <div className="flex flex-wrap gap-2" role="tablist" aria-label="Module role">
                {BOARD_ROLES.map((role) => (
                  <button
                    key={role}
                    type="button"
                    role="tab"
                    aria-selected={moduleRole === role}
                    data-testid={`training-matrix-module-role-${role}`}
                    className={`px-3 py-1.5 text-sm rounded-full border ${
                      moduleRole === role
                        ? 'bg-primary text-primary-foreground border-primary'
                        : 'border-border text-muted-foreground hover:text-foreground'
                    }`}
                    onClick={() => setRoleScope(role)}
                  >
                    {role}
                  </button>
                ))}
              </div>
              {renderEntityMetricTable('Module', 'training-matrix-module-table')}
            </div>
          ) : (
            <div className="space-y-6" data-testid="training-matrix-analytics">
              <div>
                <p className="text-sm font-medium mb-1">Compliance vs gap by Training group</p>
                <p className="text-xs text-muted-foreground mb-3">
                  In-cycle modules (Passed within frequency) vs needs action. Scope: {roleScope}.
                </p>
                <ComplianceBarChart items={analyticsBars} />
              </div>
              <div className="grid sm:grid-cols-2 gap-6">
                <div>
                  <p className="text-sm font-medium mb-2">Status mix{roleScope !== 'Overall' ? ` · ${roleScope}` : ''}</p>
                  <StatusPieChart slices={analyticsPie} />
                </div>
                <div>
                  <p className="text-sm font-medium mb-2">
                    What is due soon
                    {roleScope !== 'Overall' ? ` · ${roleScope}` : ''}
                  </p>
                  <DueForwardBars
                    d30={scopedHorizonCounts.d30}
                    d90={scopedHorizonCounts.d90}
                  />
                </div>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      <Sheet open={drawerPersonId != null} onOpenChange={(open) => !open && setDrawerPersonId(null)}>
        <SheetContent side="right" className="max-w-lg" data-testid="training-matrix-person-sheet">
          <SheetHeader>
            <SheetTitle>
              {personDetail?.engineer_display_name || personDetail?.atlas_name || 'Training detail'}
            </SheetTitle>
            <SheetDescription>
              {[personDetail?.department, personDetail?.board_role || 'Auto (Atlas)']
                .filter(Boolean)
                .join(' · ') || 'Loading…'}
            </SheetDescription>
          </SheetHeader>
          <SheetBody className="space-y-4">
            {personLoading || !personDetail ? (
              <TableSkeleton rows={4} columns={2} />
            ) : (
              <>
                <div className="grid grid-cols-4 gap-2 text-center">
                  <div className="rounded-lg border border-border p-2">
                    <p className="text-lg font-semibold">{personDetail.rollup.complete}</p>
                    <p className="text-[11px] text-muted-foreground">Complete</p>
                  </div>
                  <div className="rounded-lg border border-border p-2">
                    <p className="text-lg font-semibold">{personDetail.rollup.overdue}</p>
                    <p className="text-[11px] text-muted-foreground">Overdue</p>
                  </div>
                  <div className="rounded-lg border border-border p-2">
                    <p className="text-lg font-semibold">{personDetail.rollup.pct}%</p>
                    <p className="text-[11px] text-muted-foreground">Percent</p>
                  </div>
                  <div className="rounded-lg border border-border p-2">
                    <p className="text-lg font-semibold">{personDetail.rollup.need}</p>
                    <p className="text-[11px] text-muted-foreground">Need</p>
                  </div>
                </div>
                {personDetail.last_training_notified_at ? (
                  <p className="text-xs text-muted-foreground">
                    Last notified: {new Date(personDetail.last_training_notified_at).toLocaleString()}
                  </p>
                ) : null}
                <div className="flex flex-wrap gap-2">
                  <Button
                    type="button"
                    size="sm"
                    disabled={!personDetail.can_email || notifying}
                    onClick={() => runNotify([personDetail.atlas_name])}
                    data-testid="training-matrix-person-email"
                  >
                    <Mail className="w-3.5 h-3.5 mr-1.5" />
                    Email to complete
                  </Button>
                  <a href={personDetail.atlas_hub_url || ATLAS_HUB_URL} target="_blank" rel="noreferrer">
                    <Button type="button" size="sm" variant="outline">
                      <ExternalLink className="w-3.5 h-3.5 mr-1.5" />
                      Open Atlas
                    </Button>
                  </a>
                </div>
                {!personDetail.can_email && personDetail.email_skip_reason ? (
                  <p className="text-xs text-amber-700 dark:text-amber-400">{personDetail.email_skip_reason}</p>
                ) : null}

                <div>
                  <p className="text-sm font-medium mb-2">Needs action</p>
                  <ul className="space-y-2 text-sm">
                    {personDetail.items.filter((r) => isGapStatus(r.status)).map((r) => (
                      <li key={r.course_key} className="rounded-md border border-border px-3 py-2">
                        <div className="flex justify-between gap-2">
                          <span className="font-medium">{r.course_display_name}</span>
                          <HorizonBadge row={r} />
                        </div>
                        <p className="text-xs text-muted-foreground mt-1">
                          {r.status === 'missing' || r.status === 'pending'
                            ? 'Never completed'
                            : 'Cycle expired / overdue'}
                          {r.passed_on ? ` · Passed ${r.passed_on}` : ''}
                          {r.qgp_due_on ? ` · QGP due ${r.qgp_due_on}` : ''}
                        </p>
                      </li>
                    ))}
                    {personDetail.items.filter((r) => isGapStatus(r.status)).length === 0 ? (
                      <li className="text-muted-foreground text-xs">No open gaps.</li>
                    ) : null}
                  </ul>
                </div>

                <div>
                  <p className="text-sm font-medium mb-2">In cycle</p>
                  <ul className="space-y-2 text-sm">
                    {personDetail.items.filter((r) => isOkStatus(r.status)).map((r) => (
                      <li key={r.course_key} className="rounded-md border border-border/60 px-3 py-2">
                        <div className="flex justify-between gap-2">
                          <span>{r.course_display_name}</span>
                          <HorizonBadge row={r} />
                        </div>
                        <p className="text-xs text-muted-foreground mt-1">
                          {r.passed_on ? `Passed ${r.passed_on}` : '—'}
                          {r.qgp_due_on ? ` · OK until ${r.qgp_due_on}` : ''}
                        </p>
                      </li>
                    ))}
                  </ul>
                </div>
              </>
            )}
          </SheetBody>
        </SheetContent>
      </Sheet>

      <Sheet
        open={entityDrilldown != null}
        onOpenChange={(open) => !open && setEntityDrilldown(null)}
      >
        <SheetContent side="right" className="max-w-lg" data-testid="training-matrix-entity-sheet">
          <SheetHeader>
            <SheetTitle>{entityDrilldown?.title || 'Detail'}</SheetTitle>
            <SheetDescription>{entityDrilldown?.subtitle || ''}</SheetDescription>
          </SheetHeader>
          <SheetBody className="space-y-4">
            {entityDrilldown ? (
              <>
                <div className="grid grid-cols-4 gap-2 text-center">
                  <div className="rounded-lg border border-border p-2">
                    <p className="text-lg font-semibold">{entityDrilldown.rollup.complete}</p>
                    <p className="text-[11px] text-muted-foreground">Complete</p>
                  </div>
                  <div className="rounded-lg border border-border p-2">
                    <p className="text-lg font-semibold text-destructive">
                      {entityDrilldown.rollup.overdue}
                    </p>
                    <p className="text-[11px] text-muted-foreground">Overdue</p>
                  </div>
                  <div className="rounded-lg border border-border p-2">
                    <p className="text-lg font-semibold">{entityDrilldown.rollup.pct}%</p>
                    <p className="text-[11px] text-muted-foreground">Percent</p>
                  </div>
                  <div className="rounded-lg border border-border p-2">
                    <p className="text-lg font-semibold">{entityDrilldown.rollup.need}</p>
                    <p className="text-[11px] text-muted-foreground">Need</p>
                  </div>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Button
                    type="button"
                    size="sm"
                    disabled={notifying || entityDrilldown.rollup.filteredRows.length === 0}
                    onClick={() =>
                      runNotify([
                        ...new Set(entityDrilldown.rollup.filteredRows.map((r) => r.atlas_name)),
                      ])
                    }
                    data-testid="training-matrix-entity-email"
                  >
                    <Mail className="w-3.5 h-3.5 mr-1.5" />
                    Email people in filter
                  </Button>
                  <a href={ATLAS_HUB_URL} target="_blank" rel="noreferrer">
                    <Button type="button" size="sm" variant="outline">
                      <ExternalLink className="w-3.5 h-3.5 mr-1.5" />
                      Open Atlas
                    </Button>
                  </a>
                </div>
                <div>
                  <p className="text-sm font-medium mb-2">Needs action</p>
                  <ul className="space-y-2 text-sm">
                    {entityDrilldown.rollup.allRows
                      .filter((r) => isGapStatus(r.status))
                      .map((r) => (
                        <li key={`${r.atlas_name}-${r.course_key}`}>
                          <button
                            type="button"
                            className="w-full rounded-md border border-border px-3 py-2 text-left hover:bg-muted/40"
                            onClick={() => {
                              if (r.person_id != null) {
                                setEntityDrilldown(null)
                                setDrawerPersonId(r.person_id)
                              }
                            }}
                          >
                            <div className="flex justify-between gap-2">
                              <span className="font-medium text-primary underline-offset-2">
                                {r.engineer_display_name || r.atlas_name}
                              </span>
                              <HorizonBadge row={r} />
                            </div>
                            <p className="text-xs text-muted-foreground mt-1">
                              {r.course_display_name}
                              {r.department ? ` · ${r.department}` : ''}
                              {r.qgp_due_on ? ` · QGP due ${r.qgp_due_on}` : ''}
                            </p>
                          </button>
                        </li>
                      ))}
                    {entityDrilldown.rollup.allRows.filter((r) => isGapStatus(r.status)).length ===
                    0 ? (
                      <li className="text-muted-foreground text-xs">No open gaps.</li>
                    ) : null}
                  </ul>
                </div>
              </>
            ) : null}
          </SheetBody>
        </SheetContent>
      </Sheet>
    </div>
  )
}

export function TrainingMatrixMyTraining() {
  const { t } = useTranslation()
  const [rows, setRows] = useState<TrainingMatrixComplianceRow[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    trainingMatrixApi
      .myTraining()
      .then((res) => setRows(res.items || []))
      .catch((err) => setError(getApiErrorMessage(err)))
      .finally(() => setLoading(false))
  }, [])

  const summary = useMemo(() => myTrainingSummary(rows), [rows])

  return (
    <Card data-testid="training-matrix-my-training">
      <CardHeader className="flex flex-row items-center justify-between gap-3">
        <div>
          <p className="font-medium">{t('workforce.training_matrix.my_title', 'My training')}</p>
          <p className="text-sm text-muted-foreground">
            {t(
              'workforce.training_matrix.my_subtitle',
              'Your required modules and compliance. Incomplete items open Atlas to complete.',
            )}
          </p>
        </div>
        <AtlasCta />
      </CardHeader>
      <CardContent className="space-y-4">
        {!loading && rows.length > 0 ? (
          <div className="flex flex-wrap items-center gap-4 p-3 rounded-lg bg-muted/50 text-sm" data-testid="training-matrix-my-progress">
            <p>
              <strong>
                {summary.okCount}/{summary.total}
              </strong>{' '}
              modules complete (in cycle)
              {summary.total > 0 ? (
                <span className="text-muted-foreground">
                  {' '}
                  · {Math.round((100 * summary.okCount) / summary.total)}%
                </span>
              ) : null}
            </p>
            {summary.nextDue ? (
              <p className="text-muted-foreground">
                Next due: <strong>{summary.nextDue.course_display_name}</strong> on {summary.nextDue.qgp_due_on}
              </p>
            ) : (
              <p className="text-muted-foreground">Nothing outstanding right now.</p>
            )}
          </div>
        ) : null}
        {error ? (
          <div className="mb-4 p-3 rounded-lg bg-destructive/10 text-destructive text-sm">{error}</div>
        ) : null}
        <ComplianceTable rows={rows} loading={loading} />
      </CardContent>
    </Card>
  )
}

type MatrixGrid = Record<string, Partial<Record<BoardRole, number | null>>>

function buildGridFromRequirements(
  courseRows: { course_key: string; course_display_name: string }[],
  requirements: TrainingMatrixRequirement[],
): MatrixGrid {
  const grid: MatrixGrid = {}
  for (const row of courseRows) grid[row.course_key] = {}
  for (const req of requirements) {
    if (req.match_role_key) continue
    const role = BOARD_ROLES.find((r) => (req.match_department || '').trim().toLowerCase() === r.toLowerCase())
    if (!role) continue
    if (!grid[req.course_key]) grid[req.course_key] = {}
    grid[req.course_key][role] = req.is_active ? req.frequency_years : null
  }
  return grid
}

export function TrainingMatrixAdminPanel() {
  const { t } = useTranslation()
  const fileRef = useRef<HTMLInputElement>(null)
  const [uploading, setUploading] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [nameMaps, setNameMaps] = useState<TrainingMatrixNameMapItem[]>([])
  const [nameMapsLoaded, setNameMapsLoaded] = useState(false)
  const [requirements, setRequirements] = useState<TrainingMatrixRequirement[]>([])
  const [engineers, setEngineers] = useState<{ id: number; label: string }[]>([])
  const [courses, setCourses] = useState<{ course_key: string; display_name: string }[]>([])
  const [grid, setGrid] = useState<MatrixGrid>({})
  const [savingMatrix, setSavingMatrix] = useState(false)
  const [autoMatching, setAutoMatching] = useState(false)
  const [latestImport, setLatestImport] = useState<TrainingMatrixImport | null>(null)
  const [openUpload, setOpenUpload] = useState(true)
  const [openNameMap, setOpenNameMap] = useState(true)
  const [openMatrix, setOpenMatrix] = useState(true)
  const [hideNonMandated, setHideNonMandated] = useState(true)
  const [pendingProposals, setPendingProposals] = useState<TrainingMatrixFrequencyChangeRequest[]>([])
  const [viewerCanApprove, setViewerCanApprove] = useState(false)
  const [approverEmail, setApproverEmail] = useState('david.harris@plantexpand.com')
  const [reviewingId, setReviewingId] = useState<number | null>(null)

  const reloadProposals = () => {
    trainingMatrixApi
      .listMatrixProposals('pending')
      .then((res) => {
        setPendingProposals(res.items)
        setViewerCanApprove(Boolean(res.viewer_can_approve))
        if (res.approver_email) setApproverEmail(res.approver_email)
      })
      .catch(() => {
        setPendingProposals([])
        setViewerCanApprove(false)
      })
  }

  const reload = () => {
    setNameMapsLoaded(false)
    trainingMatrixApi
      .listNameMaps()
      .then((rows) => {
        setNameMaps(rows)
        setError(null)
      })
      .catch((err) => {
        setNameMaps([])
        setError(getApiErrorMessage(err, 'Could not load name maps (admin only).'))
      })
      .finally(() => setNameMapsLoaded(true))
    trainingMatrixApi.listRequirements().then((r) => setRequirements(r.items)).catch(() => setRequirements([]))
    trainingMatrixApi.listCourses().then(setCourses).catch(() => setCourses([]))
    trainingMatrixApi
      .getLatestImport()
      .then(setLatestImport)
      .catch(() => setLatestImport(null))
    reloadProposals()
    workforceApi
      .listEngineers({ page: '1', page_size: '500' })
      .then((res) => {
        setEngineers(
          (res.data?.items || []).map((e: EngineerProfile) => ({
            id: e.id,
            label: e.display_name?.trim() || `#${e.id}`,
          })),
        )
      })
      .catch(() => setEngineers([]))
  }

  useEffect(() => {
    reload()
    // Mount-only load for Admin panel datasets.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const courseRows = useMemo(() => {
    const byKey = new Map<string, string>()
    for (const c of courses) byKey.set(c.course_key, c.display_name)
    for (const r of requirements) if (!byKey.has(r.course_key)) byKey.set(r.course_key, r.course_display_name)
    return [...byKey.entries()]
      .map(([course_key, course_display_name]) => ({ course_key, course_display_name }))
      .sort((a, b) => a.course_display_name.localeCompare(b.course_display_name))
  }, [courses, requirements])

  const savedGrid = useMemo(() => buildGridFromRequirements(courseRows, requirements), [courseRows, requirements])

  useEffect(() => {
    setGrid(savedGrid)
    // Reset any unsaved edits whenever the server truth changes (after load/save).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [JSON.stringify(savedGrid)])

  const visibleCourseRows = useMemo(() => {
    if (!hideNonMandated) return courseRows
    return courseRows.filter((row) => {
      const cells = grid[row.course_key] || {}
      return BOARD_ROLES.some((role) => {
        const value = cells[role]
        return typeof value === 'number' && value > 0
      })
    })
  }, [courseRows, grid, hideNonMandated])

  const onUpload = async (file: File) => {
    if (!file.name.toLowerCase().endsWith('.csv')) {
      setError(
        'Upload the Atlas Training Matrix Report as CSV (.csv). Excel (.xlsx) is not accepted — export/save as CSV from Atlas first.',
      )
      return
    }
    if (latestImport) {
      const ok = window.confirm(
        `Overwrite the Atlas matrix currently on file?\n\n` +
          `Current: ${formatImportStamp(latestImport)}\n\n` +
          `This replaces last week's completion cells with the new CSV. Name maps and frequency rules are kept.`,
      )
      if (!ok) return
    }
    setUploading(true)
    setError(null)
    setMessage(null)
    try {
      const imp = await trainingMatrixApi.uploadImport(file)
      setLatestImport(imp)
      let status =
        `Imported ${imp.person_count} people, ${imp.course_count} courses. ` +
        `This file is now the live Atlas snapshot until the next upload. Name maps and frequency rules were kept.`
      // Re-apply durable maps + unique display-name matches after every weekly overwrite.
      try {
        const match = await trainingMatrixApi.autoMatchNameMaps()
        status += ` Auto-match: ${match.from_saved_maps + match.from_auto_match} linked, ${match.still_unmatched} still need a manual map.`
      } catch {
        // Upload already succeeded; manual Auto-match button remains available.
      }
      setMessage(status)
      reload()
    } catch (err) {
      setError(getApiErrorMessage(err))
    } finally {
      setUploading(false)
    }
  }

  const setCell = (courseKey: string, role: BoardRole, value: number | null) => {
    setGrid((prev) => ({
      ...prev,
      [courseKey]: { ...prev[courseKey], [role]: value },
    }))
  }

  const onProposeMatrix = () => {
    const cells: TrainingMatrixMatrixCell[] = []
    for (const row of courseRows) {
      for (const role of BOARD_ROLES) {
        const value = grid[row.course_key]?.[role] ?? null
        const original = savedGrid[row.course_key]?.[role] ?? null
        if (value === original) continue
        cells.push({
          match_department: role,
          course_key: row.course_key,
          course_display_name: row.course_display_name,
          frequency_years: value,
        })
      }
    }
    if (cells.length === 0) {
      setMessage('No changes to propose.')
      return
    }
    if (
      !window.confirm(
        `Submit ${cells.length} cell change${cells.length === 1 ? '' : 's'} for approval by ${approverEmail}? Cells stay unchanged until approved.`,
      )
    ) {
      return
    }
    setSavingMatrix(true)
    setError(null)
    setMessage(null)
    void trainingMatrixApi
      .proposeRequirementsMatrix(cells)
      .then((res) => {
        setMessage(
          `Proposed ${res.cell_count} frequency change${res.cell_count === 1 ? '' : 's'} for approval by ${approverEmail}.`,
        )
        setGrid(savedGrid)
        reloadProposals()
      })
      .catch((err) => setError(getApiErrorMessage(err, 'Could not propose frequency matrix changes.')))
      .finally(() => setSavingMatrix(false))
  }

  const onApproveProposal = (proposalId: number) => {
    if (!window.confirm('Approve these frequency changes and apply them to the live matrix?')) return
    setReviewingId(proposalId)
    setError(null)
    setMessage(null)
    void trainingMatrixApi
      .approveMatrixProposal(proposalId)
      .then((res) => {
        setMessage(
          `Approved: ${res.upserted} active cell${res.upserted === 1 ? '' : 's'}, ${res.deactivated} deactivated.`,
        )
        reload()
      })
      .catch((err) => setError(getApiErrorMessage(err, 'Could not approve frequency changes.')))
      .finally(() => setReviewingId(null))
  }

  const onRejectProposal = (proposalId: number) => {
    if (!window.confirm('Reject this frequency change request? Nothing will be applied.')) return
    setReviewingId(proposalId)
    setError(null)
    setMessage(null)
    void trainingMatrixApi
      .rejectMatrixProposal(proposalId)
      .then(() => {
        setMessage('Frequency change request rejected.')
        reloadProposals()
      })
      .catch((err) => setError(getApiErrorMessage(err, 'Could not reject frequency changes.')))
      .finally(() => setReviewingId(null))
  }

  const onAutoMatchNames = () => {
    setAutoMatching(true)
    setError(null)
    setMessage(null)
    void trainingMatrixApi
      .autoMatchNameMaps()
      .then((res) => {
        setMessage(
          `Name maps restored: ${res.from_saved_maps} from saved maps, ${res.from_auto_match} auto-matched by display name, ${res.already_mapped} already linked, ${res.still_unmatched} still unmatched.`,
        )
        setOpenNameMap(true)
        reload()
      })
      .catch((err) => setError(getApiErrorMessage(err, 'Could not auto-match Atlas names.')))
      .finally(() => setAutoMatching(false))
  }

  const unmatched = nameMaps.filter((m) => !m.mapped)
  const mappedCount = nameMaps.length - unmatched.length

  return (
    <div className="space-y-4" data-testid="training-matrix-admin">
      <AdminSection
        testId="training-matrix-admin-upload"
        title={t('workforce.training_matrix.upload_title', 'Weekly Atlas matrix upload')}
        subtitle="Admin only. Atlas CSV only (.csv). Each upload replaces the previous week's completion data and stays on file until the next upload."
        open={openUpload}
        onToggle={() => setOpenUpload((v) => !v)}
      >
        <div
          className="rounded-lg border border-border bg-muted/40 px-3 py-2 text-sm"
          data-testid="training-matrix-admin-last-upload"
        >
          {latestImport ? (
            <>
              <p className="font-medium">Last upload</p>
              <p className="text-muted-foreground">{formatImportStamp(latestImport)}</p>
              <p className="text-xs text-muted-foreground mt-1">
                {latestImport.person_count} people · {latestImport.course_count} courses · retained until next overwrite
              </p>
            </>
          ) : (
            <p className="text-muted-foreground">No Atlas matrix on file yet.</p>
          )}
        </div>
        <input
          ref={fileRef}
          type="file"
          accept=".csv,text/csv"
          className="hidden"
          onChange={(e) => {
            const f = e.target.files?.[0]
            if (f) void onUpload(f)
            e.target.value = ''
          }}
        />
        <Button
          type="button"
          disabled={uploading}
          onClick={() => fileRef.current?.click()}
          data-testid="training-matrix-upload"
        >
          <Upload className="w-4 h-4 mr-2" />
          {uploading ? 'Uploading…' : latestImport ? 'Upload CSV (overwrite)' : 'Upload CSV'}
        </Button>
        <p className="text-xs text-muted-foreground">
          Export the Training Matrix Report from Atlas as CSV. XLSX/PDF will be rejected. You will be asked
          to confirm before overwriting an existing snapshot.
        </p>
        {message ? <p className="text-sm text-foreground">{message}</p> : null}
        {error ? <p className="text-sm text-destructive">{error}</p> : null}
      </AdminSection>

      <AdminSection
        testId="training-matrix-admin-namemap"
        title="People mapping (employee + Training group)"
        subtitle={`Employees mapped ${mappedCount}/${nameMaps.length} (unmatched ${unmatched.length}). Training group overrides Atlas dept for frequency rules and board buckets; both survive weekly uploads.`}
        open={openNameMap}
        onToggle={() => setOpenNameMap((v) => !v)}
      >
        <div className="flex flex-wrap gap-2 mb-2">
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={autoMatching || !nameMapsLoaded}
            onClick={onAutoMatchNames}
            data-testid="training-matrix-auto-match"
          >
            {autoMatching ? 'Matching…' : 'Restore / auto-match names'}
          </Button>
        </div>
        <div className="space-y-2 max-h-80 overflow-y-auto">
          {nameMaps.map((row) => (
            <div
              key={row.person_id ?? row.atlas_name}
              className="flex flex-wrap items-center gap-2 text-sm"
              data-testid="training-matrix-person-row"
            >
              <span className="min-w-[10rem] font-medium">{row.atlas_name}</span>
              <span className="text-muted-foreground min-w-[8rem]" title="Atlas department (unchanged)">
                {row.department || '—'}
              </span>
              <label className="sr-only" htmlFor={`tm-role-${row.person_id}`}>
                Training group
              </label>
              <select
                id={`tm-role-${row.person_id}`}
                className="h-8 rounded-md border border-border bg-card px-2 text-sm"
                value={row.board_role_override || ''}
                disabled={!row.person_id}
                data-testid="training-matrix-board-role"
                onChange={(e) => {
                  if (!row.person_id) return
                  const next = e.target.value || null
                  void trainingMatrixApi
                    .patchPersonBoardRole(row.person_id, next)
                    .then(reload)
                    .catch((err) =>
                      setError(getApiErrorMessage(err, 'Could not update Training group.')),
                    )
                }}
              >
                <option value="">Auto (Atlas)</option>
                {BOARD_ROLES.map((role) => (
                  <option key={role} value={role}>
                    {role}
                  </option>
                ))}
              </select>
              {row.mapped ? (
                <span className="text-muted-foreground">{row.engineer_display_name || 'Mapped'}</span>
              ) : (
                <select
                  className="h-8 rounded-md border border-border bg-card px-2 text-sm"
                  defaultValue=""
                  onChange={(e) => {
                    const id = Number(e.target.value)
                    if (!id) return
                    void trainingMatrixApi.upsertNameMap(row.atlas_name, id).then(reload)
                  }}
                >
                  <option value="">Select employee…</option>
                  {engineers.map((eng) => (
                    <option key={eng.id} value={eng.id}>
                      {eng.label}
                    </option>
                  ))}
                </select>
              )}
            </div>
          ))}
          {nameMapsLoaded && nameMaps.length === 0 && !error ? (
            <p className="text-sm text-muted-foreground">
              No Atlas people yet. Upload a matrix CSV first.
            </p>
          ) : null}
        </div>
      </AdminSection>

      <AdminSection
        testId="training-matrix-admin-matrix"
        title="Frequency matrix (role x course)"
        subtitle="Select a cycle for each cell — course rows come from your Atlas courses and existing rules. Clear a cell (—) to deactivate that rule. Changes require approval before they apply."
        open={openMatrix}
        onToggle={() => setOpenMatrix((v) => !v)}
        headerRight={
          openMatrix ? (
            <div className="flex flex-wrap gap-2">
              <Button
                type="button"
                disabled={savingMatrix || courseRows.length === 0}
                onClick={onProposeMatrix}
                data-testid="training-matrix-save-matrix"
              >
                {savingMatrix ? 'Submitting…' : 'Propose for approval'}
              </Button>
            </div>
          ) : null
        }
      >
        <p className="text-xs text-muted-foreground mb-2">
          Frequency edits are dual-controlled: propose here, then {approverEmail} approves. Weekly Atlas CSV
          overwrite keeps frequency rules in the database.
        </p>
        {pendingProposals.length > 0 ? (
          <div
            className="mb-3 rounded-md border border-border bg-muted/40 px-3 py-2 space-y-2"
            data-testid="training-matrix-pending-proposals"
          >
            <p className="text-sm font-medium">
              Pending frequency approvals ({pendingProposals.length})
              {!viewerCanApprove ? (
                <span className="font-normal text-muted-foreground"> — awaiting {approverEmail}</span>
              ) : null}
            </p>
            {pendingProposals.map((proposal) => (
              <div
                key={proposal.id}
                className="flex flex-wrap items-center gap-2 text-sm"
                data-testid={`training-matrix-proposal-${proposal.id}`}
              >
                <span>
                  #{proposal.id}: {proposal.cell_count} cell
                  {proposal.cell_count === 1 ? '' : 's'}
                  {proposal.proposed_by_name || proposal.proposed_by_email
                    ? ` · ${proposal.proposed_by_name || proposal.proposed_by_email}`
                    : ''}
                </span>
                {viewerCanApprove ? (
                  <>
                    <Button
                      type="button"
                      size="sm"
                      disabled={reviewingId === proposal.id}
                      onClick={() => onApproveProposal(proposal.id)}
                      data-testid={`training-matrix-approve-${proposal.id}`}
                    >
                      {reviewingId === proposal.id ? 'Applying…' : 'Approve'}
                    </Button>
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      disabled={reviewingId === proposal.id}
                      onClick={() => onRejectProposal(proposal.id)}
                      data-testid={`training-matrix-reject-${proposal.id}`}
                    >
                      Reject
                    </Button>
                  </>
                ) : null}
              </div>
            ))}
          </div>
        ) : null}
        <div className="flex flex-wrap items-center gap-3 mb-3">
          <label
            htmlFor="training-matrix-hide-non-mandated"
            className="inline-flex items-center gap-2 text-sm"
            data-testid="training-matrix-hide-non-mandated"
          >
            <Switch
              id="training-matrix-hide-non-mandated"
              checked={hideNonMandated}
              onCheckedChange={setHideNonMandated}
            />
            Hide non-mandated courses
          </label>
          <span className="text-xs text-muted-foreground">
            Showing {visibleCourseRows.length} of {courseRows.length} courses
          </span>
        </div>
        <div className="overflow-auto max-h-[min(70vh,48rem)] border border-border rounded-md">
          <table className="w-full text-sm" data-testid="training-matrix-matrix-grid">
            <thead>
              <tr className="border-b border-border text-left text-muted-foreground sticky top-0 bg-card z-10">
                <th className="py-2 px-3">Course</th>
                {BOARD_ROLES.map((role) => (
                  <th key={role} className="py-2 px-3">
                    {role}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {visibleCourseRows.map((row) => (
                <tr key={row.course_key} className="border-b border-border/50">
                  <td className="py-1.5 px-3 font-medium">{row.course_display_name}</td>
                  {BOARD_ROLES.map((role) => (
                    <td key={role} className="py-1.5 px-3">
                      <select
                        className="h-8 rounded-md border border-border bg-card px-2 text-sm"
                        aria-label={`${row.course_display_name} — ${role}`}
                        value={grid[row.course_key]?.[role] ?? ''}
                        onChange={(e) => {
                          const raw = e.target.value
                          setCell(row.course_key, role, raw === '' ? null : Number(raw))
                        }}
                      >
                        <option value="">—</option>
                        <option value={1}>1y</option>
                        <option value={2}>2y</option>
                        <option value={3}>3y</option>
                      </select>
                    </td>
                  ))}
                </tr>
              ))}
              {courseRows.length === 0 ? (
                <tr>
                  <td colSpan={BOARD_ROLES.length + 1} className="py-6 text-center text-muted-foreground">
                    No Atlas courses yet. Upload a matrix CSV to populate rows.
                  </td>
                </tr>
              ) : null}
              {courseRows.length > 0 && visibleCourseRows.length === 0 ? (
                <tr>
                  <td colSpan={BOARD_ROLES.length + 1} className="py-6 text-center text-muted-foreground">
                    No mandated courses match the current filter. Turn off “Hide non-mandated courses” to see
                    all Atlas rows.
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </AdminSection>
    </div>
  )
}
