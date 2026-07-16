import { useMemo, useState } from 'react'
import { motion } from 'framer-motion'
import { Download, FilterX } from 'lucide-react'
import { Button } from '../ui/Button'
import { Badge } from '../ui/Badge'
import { Tooltip, TooltipContent, TooltipTrigger } from '../ui/Tooltip'
import {
  Sheet,
  SheetBody,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '../ui/Sheet'
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
  drawerRisks?: Array<{
    id: number
    reference?: string
    title: string
    residual_score: number
    inherent_score?: number
    risk_owner_name?: string
    next_review_date?: string | null
    is_within_appetite?: boolean
  }>
  drawerOpen: boolean
  onDrawerOpenChange: (open: boolean) => void
  trends?: TrendPoint[]
  topMovers?: TopMover[]
  showAppetiteOverlay?: boolean
  auditFilterActive?: boolean
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
  drawerRisks = [],
  drawerOpen,
  onDrawerOpenChange,
  trends = [],
  topMovers = [],
  showAppetiteOverlay = true,
  auditFilterActive = false,
}: RiskHeatMapProps) {
  const [boardPackBusy, setBoardPackBusy] = useState(false)
  const reduction =
    data.summary.average_inherent_score > 0
      ? Math.round(
          ((data.summary.average_inherent_score - data.summary.average_residual_score) /
            data.summary.average_inherent_score) *
            100,
        )
      : 0

  const selectedLabel = useMemo(() => {
    if (!selectedCell) return null
    const l = data.likelihood_labels[selectedCell.likelihood] ?? selectedCell.likelihood
    const i = data.impact_labels[selectedCell.impact] ?? selectedCell.impact
    const cell = data.matrix.flat().find(
      (c) => c.likelihood === selectedCell.likelihood && c.impact === selectedCell.impact,
    )
    return `${l} × ${i}${cell ? ` (${cell.risk_count})` : ''}`
  }, [selectedCell, data])

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

  const sparkMax = Math.max(1, ...trends.map((t) => t.avg_residual))

  return (
    <div className="space-y-4" data-testid="risk-heatmap">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-bold text-foreground">
            5×5 Risk Heat Map (
            {scoreType === 'inherent' ? 'Inherent' : scoreType === 'delta' ? 'Delta' : 'Residual'}{' '}
            Risk)
          </h2>
          {auditFilterActive && (
            <p className="mt-1 text-xs text-muted-foreground" data-testid="risk-heatmap-audit-scope">
              Matrix is tenant-wide; the register table below may be narrowed by audit filters.
            </p>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {(['residual', 'inherent', 'delta'] as HeatMapScoreType[]).map((mode) => (
            <Button
              key={mode}
              size="sm"
              variant={scoreType === mode ? 'default' : 'secondary'}
              onClick={() => onScoreTypeChange(mode)}
              data-testid={`risk-heatmap-score-${mode}`}
            >
              {mode === 'residual' ? 'Residual' : mode === 'inherent' ? 'Inherent' : 'Delta'}
            </Button>
          ))}
          <Button
            size="sm"
            variant={focusMode === 'appetite' ? 'default' : 'secondary'}
            onClick={() => onFocusModeChange(focusMode === 'appetite' ? 'none' : 'appetite')}
            data-testid="risk-heatmap-focus-appetite"
          >
            Focus appetite
          </Button>
          <Button
            size="sm"
            variant={focusMode === 'overdue' ? 'default' : 'secondary'}
            onClick={() => onFocusModeChange(focusMode === 'overdue' ? 'none' : 'overdue')}
            data-testid="risk-heatmap-focus-overdue"
          >
            Focus overdue
          </Button>
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

      <div className="flex flex-col gap-8 lg:flex-row">
        <div className="flex-grow overflow-x-auto">
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
                    const isSelected =
                      selectedCell?.likelihood === cell.likelihood &&
                      selectedCell?.impact === cell.impact
                    const dimEmpty = focusMode !== 'none' && cell.risk_count === 0
                    const highlight =
                      (focusMode === 'appetite' && (cell.outside_appetite_count ?? 0) > 0) ||
                      (focusMode === 'overdue' && (cell.overdue_count ?? 0) > 0)
                    const intensity = cell.intensity ?? (cell.risk_count > 0 ? 0.55 : 0.2)
                    const opacity = dimEmpty ? 0.22 : 0.45 + intensity * 0.55
                    return (
                      <Tooltip key={`${cell.likelihood}-${cell.impact}`}>
                        <TooltipTrigger asChild>
                          <motion.button
                            type="button"
                            layout
                            transition={{ duration: 0.25 }}
                            className={cn(
                              'm-0.5 flex h-16 w-20 flex-col items-center justify-center rounded-lg border-2 transition-all',
                              'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                              isSelected ? 'border-foreground ring-2 ring-ring' : 'border-transparent',
                              highlight && 'ring-2 ring-warning',
                              showAppetiteOverlay &&
                                cell.above_appetite_band &&
                                'outline outline-2 outline-offset-[-2px] outline-dashed outline-foreground/70',
                            )}
                            style={{
                              backgroundColor: cell.color,
                              opacity,
                            }}
                            aria-label={`${data.likelihood_labels[cell.likelihood]} by ${data.impact_labels[cell.impact]}, score ${cell.score}, ${cell.risk_count} risks`}
                            data-testid={`risk-heatmap-cell-${cell.likelihood}-${cell.impact}`}
                            onClick={() => onCellSelect(cell)}
                          >
                            <span className="text-lg font-bold text-white">{cell.score}</span>
                            {cell.risk_count > 0 && (
                              <span className="text-xs text-white/90">
                                ({cell.risk_count})
                              </span>
                            )}
                            {scoreType === 'delta' && (cell.movers?.length ?? 0) > 0 && (
                              <span className="text-[10px] text-white/90">↓{cell.movers?.length}</span>
                            )}
                          </motion.button>
                        </TooltipTrigger>
                        <TooltipContent className="max-w-xs space-y-1">
                          <p className="font-semibold">
                            {data.likelihood_labels[cell.likelihood]} ×{' '}
                            {data.impact_labels[cell.impact]}
                          </p>
                          <p>
                            {cell.risk_count} risk{cell.risk_count === 1 ? '' : 's'} · score{' '}
                            {cell.score}
                          </p>
                          {(cell.overdue_count ?? 0) > 0 && (
                            <p>{cell.overdue_count} overdue review</p>
                          )}
                          {(cell.outside_appetite_count ?? 0) > 0 && (
                            <p>{cell.outside_appetite_count} outside appetite</p>
                          )}
                          {(cell.owners_sample?.length ?? 0) > 0 && (
                            <p>Owners: {cell.owners_sample?.join(', ')}</p>
                          )}
                          {(cell.risk_titles?.length ?? 0) > 0 && (
                            <ul className="list-disc pl-4">
                              {cell.risk_titles.slice(0, 5).map((t) => (
                                <li key={t}>{t}</li>
                              ))}
                            </ul>
                          )}
                        </TooltipContent>
                      </Tooltip>
                    )
                  })}
                </div>
              ))}
              <div className="mt-2 text-center text-xs text-muted-foreground">IMPACT →</div>
            </div>
          </div>
        </div>

        <div className="w-full space-y-4 lg:w-64">
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
                  Dashed outline = above appetite threshold (
                  {data.appetite_overlay.threshold})
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
                {trends.map((t) => (
                  <div
                    key={t.month}
                    title={`${t.month}: ${t.avg_residual.toFixed(1)}`}
                    className="flex-1 rounded-t bg-primary/70"
                    style={{ height: `${Math.max(8, (t.avg_residual / sparkMax) * 100)}%` }}
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

      <Sheet open={drawerOpen} onOpenChange={onDrawerOpenChange}>
        <SheetContent side="right" data-testid="risk-heatmap-cell-sheet">
          <SheetHeader>
            <SheetTitle>Cell risks</SheetTitle>
            <SheetDescription>
              {selectedLabel ?? 'Select a cell to inspect ranked risks'}
            </SheetDescription>
          </SheetHeader>
          <SheetBody className="space-y-3">
            {selectedCell && (
              <Button
                size="sm"
                variant="secondary"
                onClick={() => {
                  const cell = data.matrix
                    .flat()
                    .find(
                      (c) =>
                        c.likelihood === selectedCell.likelihood &&
                        c.impact === selectedCell.impact,
                    )
                  if (cell) onShowInRegister(cell)
                }}
              >
                Show in register
              </Button>
            )}
            {drawerRisks.length === 0 ? (
              <p className="text-sm text-muted-foreground">No risks in this cell.</p>
            ) : (
              <ul className="space-y-3">
                {drawerRisks.map((r) => (
                  <li
                    key={r.id}
                    className="rounded-lg border border-border p-3"
                    data-testid={`risk-heatmap-drawer-risk-${r.id}`}
                  >
                    <button
                      type="button"
                      className="text-left font-medium text-primary hover:underline"
                      onClick={() => onOpenRisk?.(r.id)}
                    >
                      {r.reference ? `${r.reference} · ` : ''}
                      {r.title}
                    </button>
                    <div className="mt-1 flex flex-wrap gap-2 text-xs text-muted-foreground">
                      <span>Residual {r.residual_score}</span>
                      {typeof r.inherent_score === 'number' && (
                        <span>Inherent {r.inherent_score}</span>
                      )}
                      {r.risk_owner_name && <span>{r.risk_owner_name}</span>}
                      {r.is_within_appetite === false && (
                        <Badge variant="destructive">Outside appetite</Badge>
                      )}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </SheetBody>
        </SheetContent>
      </Sheet>
    </div>
  )
}
