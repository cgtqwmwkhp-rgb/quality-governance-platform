import { useMemo, useState } from 'react'
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
import {
  StandardsCellHoverPreview,
  type CellVerdictStub,
} from './StandardsCellHoverPreview'
import {
  filterClauseCatalogueRows,
  MATRIX_PRESET_IDS,
  STANDARDS_MATRIX_FRAMEWORKS,
  visibleFrameworks,
  type CatalogueRowLike,
  type FrameworkId,
  type MatrixPresetId,
} from './standardsMatrixFilters'
import type { EvidenceWorkspaceSelection } from './EvidenceWorkspaceHost'

/** Placeholder catalogue rows — clearly stubbed for PR-B live clause joins. */
const STUB_CATALOGUE_ROWS: CatalogueRowLike[] = [
  {
    id: 'stub-4.1',
    kind: 'standard',
    clauseNumber: '4.1',
    title: 'Understanding the organization and its context',
  },
  {
    id: 'stub-4.2',
    kind: 'standard',
    clauseNumber: '4.2',
    title: 'Understanding the needs and expectations of interested parties',
  },
  {
    id: 'stub-5.1',
    kind: 'standard',
    clauseNumber: '5.1',
    title: 'Leadership and commitment',
  },
  {
    id: 'stub-6.1',
    kind: 'standard',
    clauseNumber: '6.1',
    title: 'Actions to address risks and opportunities',
  },
  {
    id: 'stub-7.2',
    kind: 'standard',
    clauseNumber: '7.2',
    title: 'Competence',
  },
  {
    id: 'stub-8.1',
    kind: 'standard',
    clauseNumber: '8.1',
    title: 'Operational planning and control',
  },
  {
    id: 'stub-9.1',
    kind: 'standard',
    clauseNumber: '9.1',
    title: 'Monitoring, measurement, analysis and evaluation',
  },
  {
    id: 'stub-10.2',
    kind: 'standard',
    clauseNumber: '10.2',
    title: 'Nonconformity and corrective action',
  },
  // Scheme identity shells — quarantined from clause catalogue display when kind is present
  { id: 'stub-uvdb-shell', kind: 'scheme', frameworkId: 'uvdb', clauseNumber: 'UVDB', title: 'UVDB scheme shell' },
  { id: 'stub-pm-shell', kind: 'scheme', frameworkId: 'pm', clauseNumber: 'PM', title: 'Planet Mark scheme shell' },
]

const STUB_VERDICTS: CellVerdictStub[] = ['covered', 'partial', 'gap', 'unknown']

function stubVerdictFor(clauseNumber: string, frameworkId: FrameworkId): CellVerdictStub {
  const hash = [...`${clauseNumber}:${frameworkId}`].reduce((acc, ch) => acc + ch.charCodeAt(0), 0)
  return STUB_VERDICTS[hash % STUB_VERDICTS.length]
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

export interface StandardsMatrixShellProps {
  initialFrameworkId?: FrameworkId | null
  initialClause?: string | null
  onSelectCell: (selection: EvidenceWorkspaceSelection) => void
  selected?: EvidenceWorkspaceSelection | null
}

/**
 * Filterable Standards matrix chrome (Wave 1 PR-A).
 * Cell values are honest placeholders until PR-B live graph joins.
 */
export function StandardsMatrixShell({
  initialFrameworkId = null,
  initialClause = null,
  onSelectCell,
  selected = null,
}: StandardsMatrixShellProps) {
  const { t } = useTranslation()
  const [preset, setPreset] = useState<MatrixPresetId>('core')
  const [columnFilters, setColumnFilters] = useState<FrameworkId[]>(() =>
    initialFrameworkId ? [initialFrameworkId] : [],
  )

  const columns = useMemo(() => visibleFrameworks(preset, columnFilters), [preset, columnFilters])

  const catalogueRows = useMemo(() => {
    const rows = filterClauseCatalogueRows(STUB_CATALOGUE_ROWS)
    if (!initialClause) return rows
    const needle = initialClause.trim().toLowerCase()
    const matched = rows.filter(
      (row) =>
        (row.clauseNumber || '').toLowerCase() === needle ||
        (row.clauseNumber || '').toLowerCase().startsWith(needle),
    )
    return matched.length > 0 ? matched : rows
  }, [initialClause])

  const toggleFramework = (id: FrameworkId) => {
    setColumnFilters((prev) => {
      if (prev.includes(id)) return prev.filter((x) => x !== id)
      return [...prev, id]
    })
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
              defaultValue: 'Filter frameworks and open a clause workspace. Live coverage joins arrive in PR-B.',
            })}
          </p>
          <Badge variant="outline" className="mt-2" data-testid="standards-matrix-stub-badge">
            {t('compliance.standards_matrix.stub_badge', { defaultValue: 'PR-B stub cells' })}
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
                      ? t('compliance.standards_matrix.scheme_column_note', {
                          defaultValue: 'Scheme identity column — quarantined from clause catalogue rows',
                        })
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
                  {columns.map((col) => (
                    <th
                      key={col.id}
                      className="px-2 py-2 text-center text-xs font-semibold text-muted-foreground whitespace-nowrap"
                    >
                      {col.shortLabel}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {catalogueRows.map((row) => {
                  const clauseNumber = row.clauseNumber || row.id
                  const title = row.title || clauseNumber
                  return (
                    <tr key={row.id} className="border-b border-border/60">
                      <td className="sticky left-0 z-10 bg-card px-3 py-2 text-sm">
                        <div className="font-medium text-foreground">{clauseNumber}</div>
                        <div className="text-xs text-muted-foreground truncate max-w-[220px]">{title}</div>
                      </td>
                      {columns.map((col) => {
                        const verdict = stubVerdictFor(clauseNumber, col.id)
                        const isSelected =
                          selected?.frameworkId === col.id && selected?.clauseNumber === clauseNumber
                        return (
                          <td key={col.id} className="px-1.5 py-1.5 text-center">
                            <Tooltip>
                              <TooltipTrigger asChild>
                                <button
                                  type="button"
                                  className={cn(
                                    'mx-auto flex h-9 w-full max-w-[4.5rem] items-center justify-center rounded-md border text-[10px] font-medium transition-colors',
                                    cellTone(verdict),
                                    isSelected && 'ring-2 ring-primary',
                                  )}
                                  onClick={() =>
                                    onSelectCell({
                                      frameworkId: col.id,
                                      clauseNumber,
                                      clauseTitle: title,
                                    })
                                  }
                                  data-testid={`standards-matrix-cell-${col.id}-${clauseNumber}`}
                                  aria-label={`${col.label} ${clauseNumber}`}
                                >
                                  {t(`compliance.standards_matrix.verdict.${verdict}`, {
                                    defaultValue: verdict,
                                  })}
                                </button>
                              </TooltipTrigger>
                              <TooltipContent side="top" className="p-3">
                                <StandardsCellHoverPreview
                                  frameworkLabel={col.label}
                                  clauseNumber={clauseNumber}
                                  clauseTitle={title}
                                  verdict={verdict}
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
