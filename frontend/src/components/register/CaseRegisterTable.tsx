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
 *  - Once there is room, the table is `table-fixed`, so column widths come from
 *    the headers and no cell can widen the table. Long values wrap or clamp
 *    inside their own column instead of stealing space from their neighbours.
 *  - Before then the same markup restyles into stacked cards, each cell
 *    carrying its own visible label, so every column survives a narrow
 *    viewport.
 *
 * "Room" is `xl`, not `lg`, because the register never gets the whole viewport:
 * `Layout` gives the sidebar 288px and the page 32px of padding either side, so
 * a 1024px screen leaves a 672px table — not enough for six or seven columns
 * even with perfect widths. 1280px leaves 928px, which is. Registers carrying
 * an inline action column wait for `2xl`; see `layout` below.
 *
 * The `overflow-x-auto` wrapper is kept only as a safety valve for content with
 * a hard `min-width`; with `table-fixed` there is nothing for it to scroll.
 *
 * Row activation (PX-173 / PX-200):
 *
 *  - The row stays a plain table row (no `role="button"`). Invalid ARIA on a
 *    `<tr>` confused assistive tech into announcing a button while only the
 *    styled reference looked clickable.
 *  - Mouse: the whole row still opens via `onOpenRow` so title/date cells work.
 *  - Keyboard / new-tab: each register renders a real `<Link>` in the reference
 *    cell (`CaseRegisterReferenceLink`). Enter/Space on a focused row remains a
 *    convenience for the PX-008 contract in `Incidents.test.tsx`.
 *  - Stacked layout still drops implicit table roles below `xl`; that is the
 *    trade for keeping every column on screen (PX-288).
 */

/** Layout intent for a column. Drives its width, wrapping and clamping. */
export type CaseRegisterColumnWidth = 'reference' | 'text' | 'badge' | 'date' | 'action'

/**
 * Every class that switches between the stacked and table layouts, for each
 * breakpoint the register can use. Written out rather than composed, because
 * Tailwind only ships classes it can find as whole strings in the source.
 *
 * `reference` is 176px: the longest reference the platform mints is eighteen
 * monospace characters (`INC-2026-CACDA723` and friends), which measures 141px
 * and has to sit on one line inside the cell's 32px of padding.
 */
interface RegisterLayoutClasses {
  table: string
  thead: string
  tbody: string
  emptyRow: string
  emptyCell: string
  row: string
  cell: string
  stackedLabel: string
  width: Record<CaseRegisterColumnWidth, string>
}

const LAYOUT: Record<'xl' | '2xl', RegisterLayoutClasses> = {
  xl: {
    table: 'block w-full xl:table xl:table-fixed',
    thead: 'hidden xl:table-header-group',
    tbody: 'block xl:table-row-group',
    emptyRow: 'block xl:table-row',
    emptyCell: 'block xl:table-cell',
    row: 'block border-b border-border py-2 transition-colors last:border-b-0 xl:table-row xl:py-0',
    cell: 'flex items-baseline gap-3 px-4 py-1 text-sm xl:table-cell xl:py-3 xl:align-middle',
    stackedLabel:
      'w-28 shrink-0 text-xs font-semibold uppercase tracking-wider text-muted-foreground xl:hidden',
    width: { reference: 'xl:w-44', text: '', badge: 'xl:w-32', date: 'xl:w-28', action: 'xl:w-64' },
  },
  '2xl': {
    table: 'block w-full 2xl:table 2xl:table-fixed',
    thead: 'hidden 2xl:table-header-group',
    tbody: 'block 2xl:table-row-group',
    emptyRow: 'block 2xl:table-row',
    emptyCell: 'block 2xl:table-cell',
    row: 'block border-b border-border py-2 transition-colors last:border-b-0 2xl:table-row 2xl:py-0',
    cell: 'flex items-baseline gap-3 px-4 py-1 text-sm 2xl:table-cell 2xl:py-3 2xl:align-middle',
    stackedLabel:
      'w-28 shrink-0 text-xs font-semibold uppercase tracking-wider text-muted-foreground 2xl:hidden',
    width: {
      reference: '2xl:w-44',
      text: '',
      badge: '2xl:w-32',
      date: '2xl:w-28',
      action: '2xl:w-64',
    },
  },
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

  // An inline action column costs 256px and comes with an extra column of its
  // own, which leaves the free-text columns around 40px each at `xl`. Wait for
  // the next breakpoint rather than ship a table nobody can read.
  const layout = columns.some((column) => column.width === 'action') ? LAYOUT['2xl'] : LAYOUT.xl

  return (
    <div className={cn('w-full overflow-x-auto', className)}>
      <table className={layout.table} aria-label={label}>
        <thead className={layout.thead}>
          <tr className="border-b border-border">
            {columns.map((column) => (
              <th
                key={column.key}
                scope="col"
                className={cn(
                  'px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-muted-foreground',
                  layout.width[column.width ?? 'text'],
                )}
              >
                {column.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className={layout.tbody}>
          {rows.length === 0 ? (
            <tr className={layout.emptyRow}>
              <td colSpan={columns.length} className={layout.emptyCell}>
                {empty}
              </td>
            </tr>
          ) : (
            rows.map((row) => (
              <tr
                key={rowKey(row)}
                data-testid={rowTestId}
                className={cn(layout.row, interactive && 'cursor-pointer hover:bg-surface')}
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
                tabIndex={interactive ? 0 : undefined}
                aria-label={interactive ? rowLabel?.(row) : undefined}
              >
                {columns.map((column) => {
                  const width = column.width ?? 'text'
                  return (
                    <td
                      key={column.key}
                      data-testid={column.cellTestId?.(row)}
                      className={layout.cell}
                      onClick={
                        column.isolateClicks ? (event) => event.stopPropagation() : undefined
                      }
                    >
                      {column.hideStackedLabel ? null : (
                        <span className={layout.stackedLabel}>{column.header}</span>
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
