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
 *  - At `xl` and above the table is `table-fixed`, so column widths come from
 *    the headers and no cell can widen the table. Long values wrap or clamp
 *    inside their own column instead of stealing space from their neighbours.
 *  - Below `xl` the same markup restyles into stacked cards, each cell carrying
 *    its own visible label, so every column survives a narrow viewport.
 *
 * `xl` rather than `lg` because the register never gets the whole viewport:
 * `Layout` gives the sidebar 288px and the page 32px of padding either side, so
 * a 1024px screen leaves a 672px table — not enough for six or seven columns
 * even with perfect widths. 1280px leaves 928px, which is.
 *
 * The `overflow-x-auto` wrapper is kept only as a safety valve for content with
 * a hard `min-width`; with `table-fixed` there is nothing for it to scroll.
 */

/** Layout intent for a column. Drives its width, wrapping and clamping. */
export type CaseRegisterColumnWidth = 'reference' | 'text' | 'badge' | 'date' | 'action'

/**
 * Fixed widths for the header cells; only meaningful once `table-fixed` is on.
 * Columns left `text` share whatever is left over, equally.
 *
 * `reference` is 176px because the longest reference in the platform is a near
 * miss — `NM-2026-20033D1D`, sixteen monospace characters — and it has to fit
 * on one line with the cell's 32px of padding.
 */
const HEADER_WIDTH_CLASS: Record<CaseRegisterColumnWidth, string> = {
  reference: 'xl:w-44',
  text: '',
  badge: 'xl:w-32',
  date: 'xl:w-28',
  action: 'xl:w-64',
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
      {/*
        Explicit roles because the stacked layout drops every element to
        `display: block`, and a browser strips a table's implicit roles the
        moment its display stops being table-like. Rows are the exception: an
        activatable row keeps the `role="button"` the registers already used.
      */}
      <table className="block w-full xl:table xl:table-fixed" role="table" aria-label={label}>
        <thead className="hidden xl:table-header-group" role="rowgroup">
          <tr className="border-b border-border" role="row">
            {columns.map((column) => (
              <th
                key={column.key}
                scope="col"
                role="columnheader"
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
        <tbody className="block xl:table-row-group" role="rowgroup">
          {rows.length === 0 ? (
            <tr className="block xl:table-row" role="row">
              <td colSpan={columns.length} className="block xl:table-cell" role="cell">
                {empty}
              </td>
            </tr>
          ) : (
            rows.map((row) => (
              <tr
                key={rowKey(row)}
                data-testid={rowTestId}
                className={cn(
                  'block border-b border-border py-2 transition-colors last:border-b-0 xl:table-row xl:py-0',
                  interactive && 'cursor-pointer hover:bg-surface',
                )}
                onClick={onOpenRow ? () => onOpenRow(row) : undefined}
                onKeyDown={
                  onOpenRow
                    ? (event) => {
                        // Only the row's own keystrokes open it. Without this, a
                        // space typed into the owner-search box inside a cell
                        // bubbles up here and navigates the user off the page.
                        if (event.target !== event.currentTarget) return
                        if (event.key === 'Enter' || event.key === ' ') {
                          event.preventDefault()
                          onOpenRow(row)
                        }
                      }
                    : undefined
                }
                role={interactive ? 'button' : 'row'}
                tabIndex={interactive ? 0 : undefined}
                aria-label={interactive ? rowLabel?.(row) : undefined}
              >
                {columns.map((column) => {
                  const width = column.width ?? 'text'
                  return (
                    <td
                      key={column.key}
                      data-testid={column.cellTestId?.(row)}
                      className="flex items-baseline gap-3 px-4 py-1 text-sm xl:table-cell xl:py-3 xl:align-middle"
                      onClick={
                        column.isolateClicks ? (event) => event.stopPropagation() : undefined
                      }
                    >
                      {column.hideStackedLabel ? null : (
                        <span className="w-28 shrink-0 text-xs font-semibold uppercase tracking-wider text-muted-foreground xl:hidden">
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
