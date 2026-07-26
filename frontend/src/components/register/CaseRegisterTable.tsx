import * as React from 'react'
import { cn } from '../../helpers/utils'

/**
 * One table for every case register — incidents, near misses, complaints, RTAs.
 *
 * Each register grew its own `<table className="w-full">` inside an
 * `overflow-x-auto` wrapper. Auto table layout sizes a column to its widest
 * content, so a single record with a long unbroken string widened its column
 * past the viewport and pushed every column to its right out of sight for the
 * whole register (PX-147), references wrapped across three lines while the date
 * column was clipped (PX-205), and on a tablet or phone a controller saw a
 * reference and nothing else (PX-288). `overflow-x-auto` hid all of that behind
 * a scrollbar most people never find.
 *
 * Two rules fix it and both live here rather than in four page files:
 *
 *  - At `lg` and above the table is `table-fixed`, so column widths come from
 *    the headers and no cell can widen the table. Long values wrap or clamp
 *    inside their own column instead of stealing space from their neighbours.
 *  - Below `lg` the same markup restyles into stacked cards, each cell carrying
 *    its own visible label, so every column survives a narrow viewport.
 *
 * The `overflow-x-auto` wrapper is kept only as a safety valve for content with
 * a hard `min-width`; with `table-fixed` there is nothing for it to scroll.
 */

/** Layout intent for a column. Drives its width, wrapping and clamping. */
export type CaseRegisterColumnWidth = 'reference' | 'text' | 'badge' | 'date' | 'action'

/** Fixed widths applied to the header cells; only meaningful once `table-fixed` is on. */
const HEADER_WIDTH_CLASS: Record<CaseRegisterColumnWidth, string> = {
  reference: 'lg:w-40',
  text: '',
  badge: 'lg:w-36',
  date: 'lg:w-36',
  action: 'lg:w-64',
}

/**
 * How a cell's content behaves once its column can no longer grow.
 *
 * `text` clamps to two lines *and* breaks long words: `break-words` alone still
 * renders a 214-character token as a very tall cell, and `line-clamp` alone
 * cannot break a token that has no wrap opportunity in it.
 */
const CONTENT_CLASS: Record<CaseRegisterColumnWidth, string> = {
  reference: 'whitespace-nowrap',
  text: 'break-words line-clamp-2',
  badge: 'break-words',
  date: 'whitespace-nowrap',
  action: '',
}

export interface CaseRegisterColumn<T> {
  /** Stable identity; also the React key. */
  key: string
  /** Translated header. Also used as the cell label in the stacked layout. */
  header: string
  render: (row: T) => React.ReactNode
  /** Defaults to `text`. */
  width?: CaseRegisterColumnWidth
  /** Interactive cell — clicks inside it must not open the row. */
  isolateClicks?: boolean
  /** Suppress the stacked-layout label for cells that already speak for themselves. */
  hideStackedLabel?: boolean
  cellTestId?: (row: T) => string
}

export interface CaseRegisterTableProps<T> {
  columns: CaseRegisterColumn<T>[]
  rows: T[]
  rowKey: (row: T) => string | number
  /** Accessible name for the table, e.g. "Incidents". */
  label: string
  /** Rendered across the full row width when `rows` is empty. */
  empty: React.ReactNode
  /** Opens the record. Makes the whole row activatable by click, Enter and Space. */
  onOpenRow?: (row: T) => void
  /** Accessible name for an activatable row. Required in practice when `onOpenRow` is set. */
  rowLabel?: (row: T) => string
  rowTestId?: string
  className?: string
}

export function CaseRegisterTable<T>({
  columns,
  rows,
  rowKey,
  label,
  empty,
  onOpenRow,
  rowLabel,
  rowTestId,
  className,
}: CaseRegisterTableProps<T>) {
  const interactive = Boolean(onOpenRow)

  return (
    <div className={cn('w-full overflow-x-auto', className)}>
      <table className="w-full lg:table-fixed" aria-label={label}>
        <thead className="hidden lg:table-header-group">
          <tr className="border-b border-border">
            {columns.map((column) => (
              <th
                key={column.key}
                scope="col"
                className={cn(
                  'px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-muted-foreground',
                  HEADER_WIDTH_CLASS[column.width ?? 'text'],
                )}
              >
                {column.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="block lg:table-row-group">
          {rows.length === 0 ? (
            <tr className="block lg:table-row">
              <td colSpan={columns.length} className="block lg:table-cell">
                {empty}
              </td>
            </tr>
          ) : (
            rows.map((row) => (
              <tr
                key={rowKey(row)}
                data-testid={rowTestId}
                className={cn(
                  'block border-b border-border py-2 transition-colors last:border-b-0 lg:table-row lg:py-0',
                  interactive && 'cursor-pointer hover:bg-surface',
                )}
                onClick={onOpenRow ? () => onOpenRow(row) : undefined}
                onKeyDown={
                  onOpenRow
                    ? (event) => {
                        if (event.key === 'Enter' || event.key === ' ') {
                          event.preventDefault()
                          onOpenRow(row)
                        }
                      }
                    : undefined
                }
                role={interactive ? 'button' : undefined}
                tabIndex={interactive ? 0 : undefined}
                aria-label={interactive ? rowLabel?.(row) : undefined}
              >
                {columns.map((column) => {
                  const width = column.width ?? 'text'
                  return (
                    <td
                      key={column.key}
                      data-testid={column.cellTestId?.(row)}
                      className="flex items-baseline gap-3 px-4 py-1 text-sm lg:table-cell lg:py-3 lg:align-middle"
                      onClick={
                        column.isolateClicks ? (event) => event.stopPropagation() : undefined
                      }
                    >
                      {column.hideStackedLabel ? null : (
                        <span className="w-28 shrink-0 text-xs font-semibold uppercase tracking-wider text-muted-foreground lg:hidden">
                          {column.header}
                        </span>
                      )}
                      <div className={cn('min-w-0 flex-1', CONTENT_CLASS[width])}>
                        {column.render(row)}
                      </div>
                    </td>
                  )
                })}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  )
}
