import { useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { motion } from 'framer-motion'
import { Download, FilterX } from 'lucide-react'
import { Button } from '../ui/Button'
import { Badge } from '../ui/Badge'
import { Tooltip, TooltipContent, TooltipTrigger } from '../ui/Tooltip'
import { cn } from '../../helpers/utils'

export type HeatMapScoreType = 'residual' | 'inherent' | 'delta'
export type HeatMapFocusMode = 'none' | 'appetite' | 'overdue'

export interface HeatMapCell {
  likelihood: number
  impact: number
  score: number
  level: string
  color: string
  risk_count: number
  risk_ids: number[]
  risk_ids_truncated?: boolean
  risk_titles: string[]
  owners_sample?: string[]
  overdue_count?: number
  outside_appetite_count?: number
  intensity?: number
  above_appetite_band?: boolean
  movers?: Array<{
    id: number
    title: string
    from: [number, number]
    to: [number, number]
    inherent_score?: number
    residual_score?: number
  }>
}

export interface HeatMapData {
  matrix: HeatMapCell[][]
  summary: {
    total_risks: number
    critical_risks: number
    high_risks: number
    medium_risks?: number
    low_risks?: number
    outside_appetite: number
    average_inherent_score: number
    average_residual_score: number
  }
  likelihood_labels: Record<number, string>
  impact_labels: Record<number, string>
  appetite_overlay?: { threshold: number; source: string }
  view_mode?: string
}

export interface HeatMapRiskDetail {
  id: number
  title: string
  reference?: string
  created_at?: string
  category?: string
  owner?: string
  inherent_score?: number
  residual_score?: number
  status?: string
  next_review_date?: string | null
}

export interface TrendPoint {
  month: string
  avg_residual: number
  avg_inherent?: number
  assessment_count?: number
}

export interface TopMover {
  id: number
  title: string
  from_score: number
  to_score: number
  delta: number
}

const SCORE_MODES: Array<{
  value: HeatMapScoreType
  label: string
  hint: string
}> = [
  {
    value: 'residual',
    label: 'After controls',
    hint: 'Place each risk by residual likelihood × impact (after existing controls).',
  },
  {
    value: 'inherent',
    label: 'Before controls',
    hint: 'Place each risk by inherent likelihood × impact (before controls).',
  },
  {
    value: 'delta',
    label: 'Movement',
    hint: 'Show the residual grid and mark cells where inherent and residual placement differ.',
  },
]

const FOCUS_MODES: Array<{
  value: HeatMapFocusMode
  label: string
  hint: string
}> = [
  {
    value: 'none',
    label: 'None',
    hint: 'Show every cell at normal emphasis.',
  },
  {
    value: 'appetite',
    label: 'Outside appetite',
    hint: 'Highlight cells with risks above appetite; dim empty cells.',
  },
  {
    value: 'overdue',
    label: 'Overdue review',
    hint: 'Highlight cells with overdue reviews; dim empty cells.',
  },
]

interface RiskHeatMapProps {
  data: HeatMapData
  scoreType: HeatMapScoreType
  focusMode: HeatMapFocusMode
  selectedCell: { likelihood: number; impact: number } | null
  onScoreTypeChange: (v: HeatMapScoreType) => void
  onFocusModeChange: (v: HeatMapFocusMode) => void
  onCellSelect: (cell: HeatMapCell) => void
  onShowInRegister: (cell: HeatMapCell) => void
  onClearCellFilter: () => void
  onOpenRisk?: (riskId: number) => void
  riskDetails?: Map<number, HeatMapRiskDetail>
  trends?: TrendPoint[]
  topMovers?: TopMover[]
  showAppetiteOverlay?: boolean
  auditFilterActive?: boolean
}

function cellKey(cell: Pick<HeatMapCell, 'likelihood' | 'impact'>) {
  return `${cell.likelihood}-${cell.impact}`
}

export function RiskHeatMap({
  data,
  scoreType,
  focusMode,
  selectedCell,
  onScoreTypeChange,
  onFocusModeChange,
  onCellSelect,
  onShowInRegister,
  onClearCellFilter,
  onOpenRisk,
  riskDetails,
  trends = [],
  topMovers = [],
  showAppetiteOverlay = true,
  auditFilterActive = false,
}: RiskHeatMapProps) {
  const { t } = useTranslation()
  const [boardPackBusy, setBoardPackBusy] = useState(false)
  const [hoverKey, setHoverKey] = useState<string | null>(null)

  const reduction =
    data.summary.average_inherent_score > 0
      ? Math.round(
          ((data.summary.average_inherent_score - data.summary.average_residual_score) /
            data.summary.average_inherent_score) *
            100,
        )
      : 0

  const selectedHeatMapCell = useMemo(() => {
    if (!selectedCell) return null
    return (
      data.matrix.flat().find(
        (c) => c.likelihood === selectedCell.likelihood && c.impact === selectedCell.impact,
      ) ?? null
    )
  }, [selectedCell, data.matrix])

  const selectedLabel = useMemo(() => {
    if (!selectedCell || !selectedHeatMapCell) return null
    const l = data.likelihood_labels[selectedCell.likelihood] ?? selectedCell.likelihood
    const i = data.impact_labels[selectedCell.impact] ?? selectedCell.impact
    return `${l} × ${i} (${selectedHeatMapCell.risk_count})`
  }, [selectedCell, selectedHeatMapCell, data.likelihood_labels, data.impact_labels])

  const railRiskEntries = useMemo(() => {
    if (!selectedHeatMapCell) return []
    return selectedHeatMapCell.risk_ids.map((id, index) => {
      const detail = riskDetails?.get(id)
      return {
        id,
        title: detail?.title ?? selectedHeatMapCell.risk_titles[index] ?? t('risk_register.heatmap.risk_fallback', { id }),
        detail,
      }
    })
  }, [selectedHeatMapCell, riskDetails, t])

  const exportBoardPack = () => {
    setBoardPackBusy(true)
    try {
      const payload = {
        exported_at: new Date().toISOString(),
        score_type: scoreType,
        summary: data.summary,
        appetite_overlay: data.appetite_overlay,
        matrix: data.matrix.map((row) =>
          row.map((c) => ({
            likelihood: c.likelihood,
            impact: c.impact,
            score: c.score,
            risk_count: c.risk_count,
            overdue_count: c.overdue_count,
            outside_appetite_count: c.outside_appetite_count,
          })),
        ),
        top_movers: topMovers,
        trends,
      }
      const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `risk-heatmap-board-pack-${new Date().toISOString().slice(0, 10)}.json`
      a.click()
      URL.revokeObjectURL(url)
      window.print()
    } finally {
      setBoardPackBusy(false)
    }
  }

  const sparkMax = Math.max(1, ...trends.map((point) => point.avg_residual))
  const scoreHeading =
    scoreType === 'inherent' ? 'Before controls' : scoreType === 'delta' ? 'Movement' : 'After controls'

  return (
    <div className="space-y-4" data-testid="risk-heatmap">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
        <div>
          <h2 className="text-xl font-bold text-foreground">5×5 Risk Heat Map</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Viewing placement: <span className="font-medium text-foreground">{scoreHeading}</span>
          </p>
          {auditFilterActive && (
            <p className="mt-1 text-xs text-muted-foreground" data-testid="risk-heatmap-audit-scope">
              Matrix is tenant-wide; the register table below may be narrowed by audit filters.
            </p>
          )}
        </div>

        <div className="flex flex-wrap items-end gap-4">
          <div>
            <p className="mb-1.5 text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Place on grid
            </p>
            <div
              role="group"
              aria-label="How risks are placed on the grid"
              className="inline-flex rounded-lg border border-border bg-muted/40 p-0.5"
            >
              {SCORE_MODES.map((mode) => (
                <Tooltip key={mode.value}>
                  <TooltipTrigger asChild>
                    <button
                      type="button"
                      className={cn(
                        'rounded-md px-3 py-1.5 text-xs font-medium transition-colors',
                        scoreType === mode.value
                          ? 'bg-primary text-primary-foreground shadow-sm'
                          : 'text-muted-foreground hover:bg-background hover:text-foreground',
                      )}
                      aria-pressed={scoreType === mode.value}
                      data-testid={`risk-heatmap-score-${mode.value}`}
                      onClick={() => onScoreTypeChange(mode.value)}
                    >
                      {mode.label}
                    </button>
                  </TooltipTrigger>
                  <TooltipContent className="max-w-[220px]">{mode.hint}</TooltipContent>
                </Tooltip>
              ))}
            </div>
          </div>

          <div>
            <p className="mb-1.5 text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Highlight
            </p>
            <div
              role="group"
              aria-label="Heat map highlight mode"
              className="inline-flex rounded-lg border border-border bg-muted/40 p-0.5"
            >
              {FOCUS_MODES.map((mode) => (
                <Tooltip key={mode.value}>
                  <TooltipTrigger asChild>
                    <button
                      type="button"
                      className={cn(
                        'rounded-md px-3 py-1.5 text-xs font-medium transition-colors',
                        focusMode === mode.value
                          ? 'bg-primary text-primary-foreground shadow-sm'
                          : 'text-muted-foreground hover:bg-background hover:text-foreground',
                      )}
                      aria-pressed={focusMode === mode.value}
                      data-testid={
                        mode.value === 'none'
                          ? 'risk-heatmap-focus-none'
                          : `risk-heatmap-focus-${mode.value === 'appetite' ? 'appetite' : 'overdue'}`
                      }
                      onClick={() => onFocusModeChange(mode.value)}
                    >
                      {mode.label}
                    </button>
                  </TooltipTrigger>
                  <TooltipContent className="max-w-[220px]">{mode.hint}</TooltipContent>
                </Tooltip>
              ))}
            </div>
          </div>

          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                size="sm"
                variant="secondary"
                onClick={exportBoardPack}
                disabled={boardPackBusy}
                data-testid="risk-heatmap-board-pack"
              >
                <Download className="mr-1 h-4 w-4" />
                Board pack
              </Button>
            </TooltipTrigger>
            <TooltipContent className="max-w-[220px]">
              Download a JSON snapshot of this matrix, summary, and top movers, then open print for a
              board pack.
            </TooltipContent>
          </Tooltip>
        </div>
      </div>

      {selectedLabel && (
        <div
          className="flex items-center gap-2 rounded-lg border border-primary/30 bg-primary/5 px-3 py-2 text-sm"
          data-testid="risk-heatmap-cell-filter-chip"
        >
          <Badge variant="default">Cell filter</Badge>
          <span className="text-foreground">{selectedLabel}</span>
          <Button size="sm" variant="ghost" onClick={onClearCellFilter} aria-label="Clear cell filter">
            <FilterX className="h-4 w-4" />
            Clear
          </Button>
        </div>
      )}

      <div className="flex flex-col gap-6 lg:flex-row lg:items-stretch">
        <div className="shrink-0 overflow-x-auto">
          <div className="flex min-w-[520px]">
            <div className="flex flex-col items-center justify-center pr-4">
              <span
                className="text-sm font-medium text-muted-foreground"
                style={{ writingMode: 'vertical-rl', transform: 'rotate(180deg)' }}
              >
                LIKELIHOOD →
              </span>
            </div>
            <div>
              <div className="flex">
                <div className="w-24" />
                {[1, 2, 3, 4, 5].map((impact) => (
                  <div key={impact} className="mb-2 w-20 text-center text-xs text-muted-foreground">
                    {data.impact_labels[impact]}
                  </div>
                ))}
              </div>
              {data.matrix.map((row, rowIndex) => (
                <div key={rowIndex} className="flex items-center">
                  <div className="w-24 pr-4 text-right text-xs text-muted-foreground">
                    {data.likelihood_labels[5 - rowIndex]}
                  </div>
                  {row.map((cell) => {
                    const key = cellKey(cell)
                    const isSelected =
                      selectedCell?.likelihood === cell.likelihood &&
                      selectedCell?.impact === cell.impact
                    const isHovered = hoverKey === key
                    const dimEmpty = focusMode !== 'none' && cell.risk_count === 0
                    const highlight =
                      (focusMode === 'appetite' && (cell.outside_appetite_count ?? 0) > 0) ||
                      (focusMode === 'overdue' && (cell.overdue_count ?? 0) > 0)
                    const intensity = cell.intensity ?? (cell.risk_count > 0 ? 0.55 : 0.2)
                    const opacity = dimEmpty ? 0.22 : 0.45 + intensity * 0.55

                    return (
                      <div key={key}>
                        <motion.button
                          type="button"
                          layout
                          transition={{ duration: 0.25 }}
                          className={cn(
                            'm-0.5 flex h-16 w-20 flex-col items-center justify-center rounded-lg border-2 transition-all',
                            'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                            isSelected ? 'border-foreground ring-2 ring-ring' : 'border-transparent',
                            isHovered && !isSelected && 'ring-2 ring-primary/60',
                            highlight && 'ring-2 ring-warning',
                            showAppetiteOverlay &&
                              cell.above_appetite_band &&
                              'outline outline-2 outline-offset-[-2px] outline-dashed outline-foreground/70',
                          )}
                          style={{
                            backgroundColor: cell.color,
                            opacity,
                          }}
                          aria-label={`${data.likelihood_labels[cell.likelihood]} by ${data.impact_labels[cell.impact]}, score ${cell.score}, ${cell.risk_count} risks${cell.risk_count === 0 ? ' (empty — selectable)' : ''}`}
                          aria-pressed={isSelected}
                          data-risk-count={cell.risk_count}
                          data-empty={cell.risk_count === 0 ? 'true' : 'false'}
                          data-testid={`risk-heatmap-cell-${cell.likelihood}-${cell.impact}`}
                          onMouseEnter={() => setHoverKey(key)}
                          onMouseLeave={() => setHoverKey(null)}
                          onFocus={() => setHoverKey(key)}
                          onBlur={() => setHoverKey(null)}
                          onClick={() => onCellSelect(cell)}
                        >
                          <span className="text-lg font-bold text-white">{cell.score}</span>
                          {cell.risk_count > 0 && (
                            <span className="text-xs text-white/90">({cell.risk_count})</span>
                          )}
                          {scoreType === 'delta' && (cell.movers?.length ?? 0) > 0 && (
                            <span className="text-[10px] text-white/90">↓{cell.movers?.length}</span>
                          )}
                        </motion.button>
                      </div>
                    )
                  })}
                </div>
              ))}
              <div className="mt-2 text-center text-xs text-muted-foreground">IMPACT →</div>
            </div>
          </div>
        </div>

        <aside
          className="flex h-[22rem] max-h-[min(22rem,55vh)] w-full min-w-0 flex-1 flex-col overflow-hidden rounded-xl border border-border bg-card lg:max-w-md"
          data-testid="risk-heatmap-detail-rail"
          aria-label={t('risk_register.heatmap.detail_rail_label')}
        >
          {!selectedHeatMapCell ? (
            <div
              className="flex flex-1 items-center justify-center p-4 text-center text-sm text-muted-foreground"
              data-testid="risk-heatmap-detail-empty"
            >
              {t('risk_register.heatmap.select_cell_prompt')}
            </div>
          ) : selectedHeatMapCell.risk_count === 0 ? (
            <div
              className="flex flex-1 flex-col"
              data-testid="risk-heatmap-detail-empty-cell"
            >
              <div
                className="shrink-0 border-b border-border px-3 py-2.5"
                data-testid="risk-heatmap-detail-header"
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-semibold text-foreground">
                      {data.likelihood_labels[selectedHeatMapCell.likelihood]} ×{' '}
                      {data.impact_labels[selectedHeatMapCell.impact]}
                    </p>
                    <p className="mt-0.5 text-[11px] text-muted-foreground">
                      {t('risk_register.n_risks', { count: 0 })}
                      {' · '}
                      {t('risk_register.score')} {selectedHeatMapCell.score}
                    </p>
                  </div>
                  <div className="flex shrink-0 flex-wrap justify-end gap-1">
                    <Button
                      size="sm"
                      variant="secondary"
                      className="h-7 px-2 text-xs"
                      data-testid="risk-heatmap-detail-show-register"
                      onClick={() => onShowInRegister(selectedHeatMapCell)}
                    >
                      {t('risk_register.heatmap.show_in_register')}
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      className="h-7 px-2 text-xs"
                      data-testid="risk-heatmap-detail-clear"
                      onClick={onClearCellFilter}
                    >
                      {t('risk_register.heatmap.clear_selection')}
                    </Button>
                  </div>
                </div>
              </div>
              <div className="flex flex-1 items-center justify-center p-4 text-center text-sm text-muted-foreground">
                No risks in this likelihood × impact band. Selection still filters the register.
              </div>
            </div>
          ) : (
            <>
              <div
                className="shrink-0 border-b border-border px-3 py-2.5"
                data-testid="risk-heatmap-detail-header"
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-semibold text-foreground">
                      {data.likelihood_labels[selectedHeatMapCell.likelihood]} ×{' '}
                      {data.impact_labels[selectedHeatMapCell.impact]}
                    </p>
                    <p className="mt-0.5 text-[11px] text-muted-foreground">
                      {t('risk_register.n_risks', { count: selectedHeatMapCell.risk_count })}
                      {' · '}
                      {t('risk_register.score')} {selectedHeatMapCell.score}
                      {(selectedHeatMapCell.overdue_count ?? 0) > 0
                        ? ` · ${selectedHeatMapCell.overdue_count} ${t('risk_register.overdue_review').toLowerCase()}`
                        : ''}
                      {(selectedHeatMapCell.outside_appetite_count ?? 0) > 0
                        ? ` · ${selectedHeatMapCell.outside_appetite_count} ${t('risk_register.outside_appetite').toLowerCase()}`
                        : ''}
                    </p>
                  </div>
                  <div className="flex shrink-0 flex-wrap justify-end gap-1">
                    <Button
                      size="sm"
                      variant="secondary"
                      className="h-7 px-2 text-xs"
                      data-testid="risk-heatmap-detail-show-register"
                      onClick={() => onShowInRegister(selectedHeatMapCell)}
                    >
                      {t('risk_register.heatmap.show_in_register')}
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      className="h-7 px-2 text-xs"
                      data-testid="risk-heatmap-detail-clear"
                      onClick={onClearCellFilter}
                    >
                      {t('risk_register.heatmap.clear_selection')}
                    </Button>
                  </div>
                </div>
              </div>

              <div
                className="min-h-0 flex-1 space-y-1 overflow-y-auto overscroll-contain p-2"
                data-testid="risk-heatmap-detail-list"
              >
                {railRiskEntries.map(({ id, title, detail }) => {
                  const metaParts = [
                    detail?.reference,
                    detail?.owner,
                    detail?.inherent_score != null ? `G ${detail.inherent_score}` : null,
                    detail?.residual_score != null ? `N ${detail.residual_score}` : null,
                    detail?.status
                      ? detail.status.replace(/_/g, ' ')
                      : null,
                  ].filter(Boolean)
                  return (
                    <article
                      key={id}
                      className="flex items-center gap-2 rounded-md border border-border/80 bg-background px-2 py-1.5"
                      data-testid={`risk-heatmap-detail-card-${id}`}
                    >
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-medium leading-snug text-foreground">
                          {title}
                        </p>
                        {metaParts.length > 0 ? (
                          <p className="mt-0.5 truncate text-[11px] capitalize leading-tight text-muted-foreground">
                            {metaParts.join(' · ')}
                          </p>
                        ) : null}
                      </div>
                      <Button
                        size="sm"
                        variant="secondary"
                        className="h-7 shrink-0 px-2 text-xs"
                        data-testid={`risk-heatmap-detail-open-${id}`}
                        onClick={() => onOpenRisk?.(id)}
                      >
                        {t('risk_register.heatmap.open')}
                      </Button>
                    </article>
                  )
                })}
                {(selectedHeatMapCell.risk_ids_truncated ||
                  selectedHeatMapCell.risk_count > railRiskEntries.length) && (
                  <p className="px-1 py-1 text-[11px] text-muted-foreground" data-testid="risk-heatmap-detail-truncated">
                    {t('risk_register.heatmap.truncated_list', {
                      shown: railRiskEntries.length,
                      total: selectedHeatMapCell.risk_count,
                    })}
                  </p>
                )}
              </div>
            </>
          )}
        </aside>

        <div className="w-full shrink-0 space-y-4 lg:w-64">
          <div className="rounded-xl bg-muted p-4">
            <h3 className="mb-3 font-semibold text-foreground">Risk Levels</h3>
            <div className="space-y-2 text-sm">
              <div className="flex items-center gap-2">
                <div className="h-4 w-4 rounded" style={{ backgroundColor: '#ef4444' }} />
                <span>Critical (17-25)</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="h-4 w-4 rounded" style={{ backgroundColor: '#f97316' }} />
                <span>High (10-16)</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="h-4 w-4 rounded" style={{ backgroundColor: '#eab308' }} />
                <span>Medium (5-9)</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="h-4 w-4 rounded" style={{ backgroundColor: '#22c55e' }} />
                <span>Low (1-4)</span>
              </div>
              {showAppetiteOverlay && data.appetite_overlay && (
                <p className="pt-2 text-xs text-muted-foreground">
                  Dashed outline = above appetite threshold ({data.appetite_overlay.threshold})
                </p>
              )}
            </div>
          </div>

          <div className="rounded-xl border border-border p-4" data-testid="risk-heatmap-summary">
            <h3 className="mb-3 font-semibold text-foreground">Summary</h3>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Total Risks</span>
                <span className="font-bold text-foreground">{data.summary.total_risks}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Critical / High</span>
                <span className="font-bold text-foreground">
                  {data.summary.critical_risks} / {data.summary.high_risks}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Avg Inherent</span>
                <span className="font-bold text-foreground">
                  {data.summary.average_inherent_score.toFixed(1)}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Avg Residual</span>
                <span className="font-bold text-primary">
                  {data.summary.average_residual_score.toFixed(1)}
                </span>
              </div>
              <div className="flex justify-between border-t border-border pt-2">
                <span className="text-muted-foreground">Risk Reduction</span>
                <span className="font-bold text-success">{reduction}%</span>
              </div>
            </div>
          </div>

          {trends.length > 0 && (
            <div className="rounded-xl border border-border p-4" data-testid="risk-heatmap-sparkline">
              <h3 className="mb-2 font-semibold text-foreground">Residual trend</h3>
              <div className="flex h-12 items-end gap-0.5">
                {trends.map((point) => (
                  <div
                    key={point.month}
                    title={`${point.month}: ${point.avg_residual.toFixed(1)}`}
                    className="flex-1 rounded-t bg-primary/70"
                    style={{ height: `${Math.max(8, (point.avg_residual / sparkMax) * 100)}%` }}
                  />
                ))}
              </div>
            </div>
          )}

          {topMovers.length > 0 && (
            <div className="rounded-xl border border-border p-4" data-testid="risk-heatmap-movers">
              <h3 className="mb-2 font-semibold text-foreground">Top movers</h3>
              <ul className="space-y-2 text-xs">
                {topMovers.slice(0, 5).map((m) => (
                  <li key={m.id} className="flex justify-between gap-2">
                    <button
                      type="button"
                      className="truncate text-left text-primary hover:underline"
                      onClick={() => onOpenRisk?.(m.id)}
                    >
                      {m.title}
                    </button>
                    <span className={m.delta < 0 ? 'text-success' : 'text-destructive'}>
                      {m.delta > 0 ? '+' : ''}
                      {m.delta}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
