import { useCallback, useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Grid3X3, Filter } from 'lucide-react'
import {
  Badge,
  Button,
  Card,
  CardContent,
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '../../components/ui'
import { cn } from '../../helpers/utils'
import { standardsCellAggregateApi, getApiErrorMessage } from '../../api/client'
import type {
  AlignmentCatalogueRow,
  AlignmentVerdict,
  CellVerdict,
} from '../../api/standardsCellAggregateTypes'
import {
  StandardsCellHoverPreview,
  type CellVerdictStub,
} from './StandardsCellHoverPreview'
import {
  chunkClausesForRequest,
  filterClauseCatalogueRows,
  MATRIX_PRESET_IDS,
  STANDARDS_MATRIX_FRAMEWORKS,
  visibleFrameworks,
  type CatalogueRowLike,
  type FrameworkId,
  type MatrixPresetId,
} from './standardsMatrixFilters'
import type { EvidenceWorkspaceSelection } from './EvidenceWorkspaceHost'

/**
 * Fallback clause axis, used only when no 5064 alignment edition has been
 * imported for the tenant (or the catalogue read fails). PR-C serves the real
 * axis from `/compliance/alignment/catalogue`; this list stays so an un-imported
 * tenant sees a working matrix rather than an empty grid, and the shell says
 * which of the two it is showing.
 */
const FALLBACK_CATALOGUE_ROWS: CatalogueRowLike[] = [
  {
    id: 'clause-4.1',
    kind: 'standard',
    clauseNumber: '4.1',
    title: 'Understanding the organization and its context',
  },
  {
    id: 'clause-4.2',
    kind: 'standard',
    clauseNumber: '4.2',
    title: 'Understanding the needs and expectations of interested parties',
  },
  {
    id: 'clause-5.1',
    kind: 'standard',
    clauseNumber: '5.1',
    title: 'Leadership and commitment',
  },
  {
    id: 'clause-6.1',
    kind: 'standard',
    clauseNumber: '6.1',
    title: 'Actions to address risks and opportunities',
  },
  {
    id: 'clause-6.1.2',
    kind: 'standard',
    clauseNumber: '6.1.2',
    title: 'Risk assessment (trap respect — links only)',
  },
  {
    id: 'clause-7.2',
    kind: 'standard',
    clauseNumber: '7.2',
    title: 'Competence',
  },
  {
    id: 'clause-8.1',
    kind: 'standard',
    clauseNumber: '8.1',
    title: 'Operational planning and control',
  },
  {
    id: 'clause-9.1',
    kind: 'standard',
    clauseNumber: '9.1',
    title: 'Monitoring, measurement, analysis and evaluation',
  },
  {
    id: 'clause-10.2',
    kind: 'standard',
    clauseNumber: '10.2',
    title: 'Nonconformity and corrective action',
  },
  // Scheme identity shells — quarantined from clause catalogue display when kind is present
  { id: 'uvdb-shell', kind: 'scheme', frameworkId: 'uvdb', clauseNumber: 'UVDB', title: 'UVDB scheme shell' },
  { id: 'pm-shell', kind: 'scheme', frameworkId: 'pm', clauseNumber: 'PM', title: 'Planet Mark scheme shell' },
]

type CellLiveState = {
  verdict: CellVerdictStub
  coverBlocked: boolean
  recurrenceRedFlag: boolean
  topEvidenceLabel?: string | null
  freshnessLabel?: string | null
  alignmentVerdict?: AlignmentVerdict | string | null
  isTrapRow?: boolean
  trapPeerCount?: number
  techGapStub?: boolean
  /** A source hit its read cap, so this cell's counts are a floor, not a total. */
  scanTruncated?: boolean
}

/** Row verdict badge tone. DIFFERENT and UNIQUE are the rows that mislead. */
function verdictTone(verdict: AlignmentVerdict | string | null | undefined): string {
  switch (verdict) {
    case 'EXACT':
      return 'border-emerald-500/40 text-emerald-600 dark:text-emerald-400'
    case 'NEAR':
      return 'border-amber-500/40 text-amber-600 dark:text-amber-400'
    case 'DIFFERENT':
      return 'border-destructive/40 text-destructive'
    case 'UNIQUE':
      return 'border-sky-500/40 text-sky-600 dark:text-sky-400'
    default:
      return 'border-border text-muted-foreground'
  }
}

function cellTone(verdict: CellVerdictStub): string {
  switch (verdict) {
    case 'covered':
      return 'bg-emerald-500/20 hover:bg-emerald-500/30 border-emerald-500/30'
    case 'partial':
      return 'bg-amber-500/20 hover:bg-amber-500/30 border-amber-500/30'
    case 'gap':
      return 'bg-destructive/15 hover:bg-destructive/25 border-destructive/30'
    default:
      return 'bg-muted/60 hover:bg-muted border-border'
  }
}

function asVerdict(value: string | undefined): CellVerdictStub {
  if (value === 'covered' || value === 'partial' || value === 'gap' || value === 'unknown') {
    return value
  }
  return 'unknown'
}

export interface StandardsMatrixShellProps {
  initialFrameworkId?: FrameworkId | null
  initialClause?: string | null
  onSelectCell: (selection: EvidenceWorkspaceSelection) => void
  selected?: EvidenceWorkspaceSelection | null
}

/**
 * Filterable Standards matrix chrome.
 * Cell verdicts from `/compliance/cell-aggregate/matrix` (PR-B live graph).
 */
export function StandardsMatrixShell({
  initialFrameworkId = null,
  initialClause = null,
  onSelectCell,
  selected = null,
}: StandardsMatrixShellProps) {
  const { t } = useTranslation()
  const [preset, setPreset] = useState<MatrixPresetId>('iso')
  const [columnFilters, setColumnFilters] = useState<FrameworkId[]>(() =>
    initialFrameworkId ? [initialFrameworkId] : [],
  )
  const [liveCells, setLiveCells] = useState<Record<string, CellLiveState>>({})
  const [liveError, setLiveError] = useState<string | null>(null)
  const [liveLoading, setLiveLoading] = useState(false)
  const [alignmentRows, setAlignmentRows] = useState<AlignmentCatalogueRow[] | null>(null)
  const [matrixVersion, setMatrixVersion] = useState<string | null>(null)

  const columns = useMemo(() => visibleFrameworks(preset, columnFilters), [preset, columnFilters])

  // PR-C: the clause axis is imported 5064 data. A failed or un-imported read
  // falls back to the static axis and the badge below says which is in use.
  useEffect(() => {
    let cancelled = false
    standardsCellAggregateApi
      .getAlignmentCatalogue()
      .then((res) => {
        if (cancelled) return
        const rows = res.data?.rows || []
        setAlignmentRows(res.data?.matrix_loaded && rows.length > 0 ? rows : [])
        setMatrixVersion(res.data?.matrix_version || null)
      })
      .catch(() => {
        if (!cancelled) {
          setAlignmentRows([])
          setMatrixVersion(null)
        }
      })
    return () => {
      cancelled = true
    }
  }, [])

  const usingImportedAxis = (alignmentRows?.length ?? 0) > 0

  const catalogueRows = useMemo(() => {
    const source: CatalogueRowLike[] = usingImportedAxis
      ? (alignmentRows as AlignmentCatalogueRow[]).map((row) => ({
          id: row.id,
          kind: row.kind || 'standard',
          clauseNumber: row.clauseNumber,
          title: row.title,
        }))
      : FALLBACK_CATALOGUE_ROWS
    const rows = filterClauseCatalogueRows(source)
    if (!initialClause) return rows
    const needle = initialClause.trim().toLowerCase()
    const matched = rows.filter(
      (row) =>
        (row.clauseNumber || '').toLowerCase() === needle ||
        (row.clauseNumber || '').toLowerCase().startsWith(needle),
    )
    return matched.length > 0 ? matched : rows
  }, [initialClause, alignmentRows, usingImportedAxis])

  const rowVerdicts = useMemo(() => {
    const map: Record<string, AlignmentCatalogueRow> = {}
    for (const row of alignmentRows || []) {
      map[row.clauseNumber] = row
    }
    return map
  }, [alignmentRows])

  /**
   * Framework-local clause numbers that differ from the printed row number
   * (e.g. ISO 45001 puts Annex SL 6.3 at 8.1.3). Used for live-cell fetch and
   * workspace open so evidence lands on the right cell.
   */
  const relocatedClauses = useMemo(() => {
    const map: Record<string, Record<string, string>> = {}
    for (const row of alignmentRows || []) {
      const perFramework: Record<string, string> = {}
      for (const [frameworkId, entry] of Object.entries(row.frameworks || {})) {
        const clause = (entry?.clause_number || '').trim()
        if (clause && clause !== row.clauseNumber) perFramework[frameworkId] = clause
      }
      if (Object.keys(perFramework).length > 0) map[row.clauseNumber] = perFramework
    }
    return map
  }, [alignmentRows])

  const cellClause = useCallback(
    (frameworkId: FrameworkId, displayClause: string) =>
      relocatedClauses[displayClause]?.[frameworkId] || displayClause,
    [relocatedClauses],
  )

  // One request for the whole grid: union of the clause numbers the visible
  // columns actually use. Asking per column would be a matrix-sized N+1.
  const requestedClauses = useMemo(() => {
    const wanted = new Set<string>()
    for (const row of catalogueRows) {
      const display = row.clauseNumber || row.id
      if (!display) continue
      for (const col of columns) wanted.add(cellClause(col.id, display))
    }
    return Array.from(wanted)
  }, [catalogueRows, columns, cellClause])

  useEffect(() => {
    const frameworks = columns.map((c) => c.id)
    if (frameworks.length === 0 || requestedClauses.length === 0) return

    let cancelled = false
    setLiveLoading(true)
    setLiveError(null)
    // The All preset is 12 columns wide, so a real imported axis passes the API's
    // per-request cell cap. Chunk it rather than let one oversized request fail the
    // whole grid into the degraded fallback.
    const chunks = chunkClausesForRequest(requestedClauses, frameworks.length)
    Promise.all(chunks.map((chunk) => standardsCellAggregateApi.getMatrix(frameworks, chunk)))
      .then((responses) => {
        if (cancelled) return
        const next: Record<string, CellLiveState> = {}
        for (const res of responses) {
          for (const cell of res.data.cells || []) {
            const key = `${cell.framework}:${cell.clause_number}`
            next[key] = {
              verdict: asVerdict(cell.verdict as CellVerdict),
              coverBlocked: Boolean(cell.cover_blocked),
              recurrenceRedFlag: Boolean(cell.recurrence_red_flag),
              topEvidenceLabel: cell.summary?.top_evidence_label,
              freshnessLabel: cell.summary?.freshness,
              alignmentVerdict: cell.alignment?.row_verdict ?? null,
              isTrapRow: Boolean(cell.alignment?.is_trap_row),
              trapPeerCount: cell.alignment?.trap_peer_count ?? 0,
              techGapStub: Boolean(cell.tech_gap?.stub),
              scanTruncated: Boolean(cell.scan_truncated),
            }
          }
        }
        setLiveCells(next)
      })
      .catch((err) => {
        if (!cancelled) {
          setLiveError(getApiErrorMessage(err))
          setLiveCells({})
        }
      })
      .finally(() => {
        if (!cancelled) setLiveLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [columns, requestedClauses])

  const toggleFramework = (id: FrameworkId) => {
    setColumnFilters((prev) => {
      if (prev.includes(id)) return prev.filter((x) => x !== id)
      return [...prev, id]
    })
  }

  const resolveCell = (frameworkId: FrameworkId, clauseNumber: string): CellLiveState => {
    const hit = liveCells[`${frameworkId}:${cellClause(frameworkId, clauseNumber)}`]
    if (hit) return hit
    return {
      verdict: 'unknown',
      coverBlocked: false,
      recurrenceRedFlag: false,
      topEvidenceLabel: null,
      freshnessLabel: null,
      alignmentVerdict: rowVerdicts[clauseNumber]?.verdict ?? null,
      isTrapRow: Boolean(rowVerdicts[clauseNumber]?.is_trap),
      trapPeerCount: rowVerdicts[clauseNumber]?.trap_pair_count ?? 0,
      techGapStub: false,
      scanTruncated: false,
    }
  }

  return (
    <div className="space-y-4" data-testid="standards-matrix-shell">
      <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold text-foreground flex items-center gap-2">
            <Grid3X3 className="w-5 h-5 text-primary" aria-hidden="true" />
            {t('compliance.standards_matrix.title', { defaultValue: 'Standards matrix' })}
          </h2>
          <p className="text-sm text-muted-foreground mt-1">
            {t('compliance.standards_matrix.subtitle', {
              defaultValue:
                'Filter frameworks and open a clause workspace. Cells reflect live audits, NC, actions, risks, and certs.',
            })}
          </p>
          <Badge
            variant="outline"
            className="mt-2"
            data-testid={liveError ? 'standards-matrix-degraded-badge' : 'standards-matrix-live-badge'}
          >
            {liveLoading
              ? t('compliance.standards_matrix.loading', { defaultValue: 'Loading live cells…' })
              : liveError
                ? t('compliance.standards_matrix.degraded', {
                    defaultValue: 'Live graph unavailable — showing unknown',
                  })
                : t('compliance.standards_matrix.live_badge', { defaultValue: 'Live graph' })}
          </Badge>
          <Badge
            variant="outline"
            className="mt-2 ml-2"
            data-testid={
              usingImportedAxis ? 'standards-matrix-axis-imported' : 'standards-matrix-axis-fallback'
            }
          >
            {usingImportedAxis
              ? t('compliance.standards_matrix.axis_imported', {
                  defaultValue: 'Clause axis: {{version}}',
                  version: matrixVersion || 'imported matrix',
                })
              : t('compliance.standards_matrix.axis_fallback', {
                  defaultValue: 'Clause axis: built-in list (no matrix imported)',
                })}
          </Badge>
        </div>

        <div className="space-y-3" data-testid="standards-matrix-filters">
          <div className="flex flex-wrap items-center gap-2">
            <Filter className="w-4 h-4 text-muted-foreground" aria-hidden="true" />
            <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
              {t('compliance.standards_matrix.presets', { defaultValue: 'Presets' })}
            </span>
            {MATRIX_PRESET_IDS.map((id) => (
              <Button
                key={id}
                type="button"
                size="sm"
                variant={preset === id ? 'default' : 'outline'}
                onClick={() => {
                  setPreset(id)
                  setColumnFilters([])
                }}
                data-testid={`standards-matrix-preset-${id}`}
              >
                {t(`compliance.standards_matrix.preset.${id}`, { defaultValue: id })}
              </Button>
            ))}
          </div>

          <div className="flex flex-wrap gap-2" aria-label={t('compliance.standards_matrix.columns_aria', { defaultValue: 'Framework columns' })}>
            {STANDARDS_MATRIX_FRAMEWORKS.map((fw) => {
              const active = columnFilters.length === 0 || columnFilters.includes(fw.id)
              const inPreset = visibleFrameworks(preset, null).some((c) => c.id === fw.id)
              return (
                <Button
                  key={fw.id}
                  type="button"
                  size="sm"
                  variant={active && inPreset ? 'secondary' : 'ghost'}
                  disabled={!inPreset}
                  onClick={() => toggleFramework(fw.id)}
                  className={cn(!inPreset && 'opacity-40')}
                  data-testid={`standards-matrix-fw-${fw.id}`}
                  title={
                    fw.kind === 'scheme'
                      ? `${fw.label} — ${t('compliance.standards_matrix.scheme_column_note', {
                          defaultValue:
                            'Scheme identity column — quarantined from clause catalogue rows',
                        })}`
                      : fw.label
                  }
                >
                  {fw.shortLabel}
                  {fw.kind === 'scheme' ? (
                    <span className="ml-1 text-[10px] text-muted-foreground">
                      {t('compliance.standards_matrix.scheme_tag', { defaultValue: 'scheme' })}
                    </span>
                  ) : null}
                </Button>
              )
            })}
          </div>
        </div>
      </div>

      <Card>
        <CardContent className="p-0 overflow-x-auto">
          <TooltipProvider delayDuration={200}>
            <table className="w-full min-w-[640px] border-collapse" data-testid="standards-matrix-table">
              <thead>
                <tr className="border-b border-border bg-muted/40">
                  <th className="sticky left-0 z-10 bg-muted/40 px-3 py-2 text-left text-xs font-semibold text-muted-foreground">
                    {t('compliance.standards_matrix.clause_col', { defaultValue: 'Clause' })}
                  </th>
                  <th className="px-2 py-2 text-left text-xs font-semibold text-muted-foreground whitespace-nowrap">
                    {t('compliance.standards_matrix.alignment_col', { defaultValue: 'Alignment' })}
                  </th>
                  {columns.map((col) => (
                    <th
                      key={col.id}
                      className="px-2 py-2 text-center text-xs font-semibold text-muted-foreground whitespace-nowrap"
                    >
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <a
                            href={col.homeUrl}
                            target="_blank"
                            rel="noreferrer noopener"
                            className="underline-offset-2 hover:underline"
                            data-testid={`standards-matrix-col-${col.id}`}
                            aria-label={t('compliance.standards_matrix.framework_home_link', {
                              defaultValue: 'Open the official {{name}} page (new tab)',
                              name: col.label,
                            })}
                            onClick={(event) => event.stopPropagation()}
                          >
                            {col.shortLabel}
                          </a>
                        </TooltipTrigger>
                        <TooltipContent side="top" className="text-xs">
                          {col.label}
                        </TooltipContent>
                      </Tooltip>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {catalogueRows.map((row) => {
                  const clauseNumber = row.clauseNumber || row.id
                  const title = row.title || clauseNumber
                  const alignmentRow = rowVerdicts[clauseNumber]
                  return (
                    <tr key={row.id} className="border-b border-border/60">
                      <td className="sticky left-0 z-10 bg-card px-3 py-2 text-sm">
                        <div className="font-medium text-foreground">{clauseNumber}</div>
                        <div className="text-xs text-muted-foreground truncate max-w-[220px]">{title}</div>
                      </td>
                      <td className="px-2 py-2 text-left">
                        {alignmentRow ? (
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <Badge
                                variant="outline"
                                className={cn('text-[10px]', verdictTone(alignmentRow.verdict))}
                                data-testid={`standards-matrix-verdict-${clauseNumber}`}
                              >
                                {alignmentRow.verdict}
                              </Badge>
                            </TooltipTrigger>
                            <TooltipContent side="right" className="max-w-sm p-3 text-xs">
                              <p className="font-medium">
                                {t('compliance.standards_matrix.verdict_row', {
                                  defaultValue: 'Source verdict: {{verdict}}',
                                  verdict: alignmentRow.row_verdict,
                                })}
                              </p>
                              {alignmentRow.is_trap ? (
                                <p className="mt-1 text-destructive">
                                  {t('compliance.standards_matrix.trap_warning', {
                                    defaultValue:
                                      'Shared clause number, different requirement — evidence cannot be crossed on {{count}} pair(s).',
                                    count: alignmentRow.trap_pair_count,
                                  })}
                                </p>
                              ) : null}
                              {alignmentRow.addition_text ? (
                                <p className="mt-1 text-muted-foreground">{alignmentRow.addition_text}</p>
                              ) : null}
                              {alignmentRow.deliverables ? (
                                <p className="mt-1 text-muted-foreground">
                                  {t('compliance.standards_matrix.deliverables', {
                                    defaultValue: 'Deliverable: {{value}}',
                                    value: alignmentRow.deliverables,
                                  })}
                                </p>
                              ) : null}
                            </TooltipContent>
                          </Tooltip>
                        ) : (
                          <span className="text-[10px] text-muted-foreground">
                            {t('compliance.standards_matrix.verdict_unknown', { defaultValue: '—' })}
                          </span>
                        )}
                      </td>
                      {columns.map((col) => {
                        const live = resolveCell(col.id, clauseNumber)
                        const cellClauseNumber = cellClause(col.id, clauseNumber)
                        const isSelected =
                          selected?.frameworkId === col.id &&
                          selected?.clauseNumber === cellClauseNumber
                        return (
                          <td key={col.id} className="px-1.5 py-1.5 text-center">
                            <Tooltip>
                              <TooltipTrigger asChild>
                                <button
                                  type="button"
                                  className={cn(
                                    'mx-auto flex h-9 w-full max-w-[4.5rem] items-center justify-center rounded-md border text-[10px] font-medium transition-colors',
                                    cellTone(live.verdict),
                                    live.recurrenceRedFlag && 'ring-1 ring-destructive',
                                    isSelected && 'ring-2 ring-primary',
                                  )}
                                  onClick={() =>
                                    onSelectCell({
                                      frameworkId: col.id,
                                      clauseNumber: cellClauseNumber,
                                      clauseTitle: title,
                                    })
                                  }
                                  data-testid={`standards-matrix-cell-${col.id}-${clauseNumber}`}
                                  aria-label={`${col.label} ${cellClauseNumber}`}
                                >
                                  {t(`compliance.standards_matrix.verdict.${live.verdict}`, {
                                    defaultValue: live.verdict,
                                  })}
                                </button>
                              </TooltipTrigger>
                              <TooltipContent side="top" className="p-3">
                                <StandardsCellHoverPreview
                                  frameworkLabel={col.label}
                                  frameworkHomeUrl={col.homeUrl}
                                  clauseNumber={cellClauseNumber}
                                  clauseTitle={title}
                                  verdict={live.verdict}
                                  topEvidenceLabel={live.topEvidenceLabel}
                                  freshnessLabel={live.freshnessLabel}
                                  coverBlocked={live.coverBlocked}
                                  recurrenceRedFlag={live.recurrenceRedFlag}
                                  isStub={Boolean(liveError)}
                                  alignmentVerdict={live.alignmentVerdict ?? null}
                                  isTrapRow={Boolean(live.isTrapRow)}
                                  techGapStub={Boolean(live.techGapStub)}
                                  scanTruncated={Boolean(live.scanTruncated)}
                                />
                              </TooltipContent>
                            </Tooltip>
                          </td>
                        )
                      })}
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </TooltipProvider>
        </CardContent>
      </Card>
    </div>
  )
}
