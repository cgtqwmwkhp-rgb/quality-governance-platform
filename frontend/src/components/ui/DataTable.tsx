import * as React from 'react'
import { cn } from '../../helpers/utils'

export type SortDirection = 'asc' | 'desc'

export interface Column<T> {
  key: string
  header: string
  render?: (row: T) => React.ReactNode
  className?: string
  sortable?: boolean
}

export interface DataTableProps<T> {
  columns: Column<T>[]
  data: T[]
  keyExtractor: (row: T) => string | number
  caption?: string
  emptyMessage?: string
  className?: string
  onRowClick?: (row: T) => void
  loading?: boolean
  stickyHeader?: boolean
  defaultSortKey?: string
  defaultSortDirection?: SortDirection
}

function DataTableInner<T>(
  {
    columns,
    data,
    keyExtractor,
    caption,
    emptyMessage = 'No data available.',
    className,
    onRowClick,
    loading,
    stickyHeader,
    defaultSortKey,
    defaultSortDirection = 'asc',
  }: DataTableProps<T>,
  ref: React.ForwardedRef<HTMLTableElement>,
) {
  const [sortKey, setSortKey] = React.useState<string | null>(defaultSortKey ?? null)
  const [sortDir, setSortDir] = React.useState<SortDirection>(defaultSortDirection)

  const handleSort = React.useCallback((key: string) => {
    setSortKey((prev) => {
      if (prev === key) {
        setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
        return key
      }
      setSortDir('asc')
      return key
    })
  }, [])

  const sortedData = React.useMemo(() => {
    if (!sortKey) return data
    const col = columns.find((c) => c.key === sortKey)
    if (!col?.sortable) return data
    return [...data].sort((a, b) => {
      const aVal = (a as Record<string, unknown>)[sortKey]
      const bVal = (b as Record<string, unknown>)[sortKey]
      if (aVal == null && bVal == null) return 0
      if (aVal == null) return 1
      if (bVal == null) return -1
      const cmp = aVal < bVal ? -1 : aVal > bVal ? 1 : 0
      return sortDir === 'asc' ? cmp : -cmp
    })
  }, [data, sortKey, sortDir, columns])

  return (
    <div className={cn('relative w-full overflow-auto', className)}>
      <table
        ref={ref}
        className="w-full caption-bottom text-sm"
        role="table"
      >
        {caption && (
          <caption className="mt-4 text-sm text-muted-foreground">{caption}</caption>
        )}
        <thead className={cn(stickyHeader && 'sticky top-0 z-10 bg-background')}>
          <tr className="border-b border-border transition-colors">
            {columns.map((col) => (
              <th
                key={col.key}
                className={cn(
                  'h-10 px-3 text-left align-middle font-medium text-muted-foreground',
                  col.sortable && 'cursor-pointer select-none hover:text-foreground',
                  col.className,
                )}
                scope="col"
                onClick={col.sortable ? () => handleSort(col.key) : undefined}
                aria-sort={
                  sortKey === col.key
                    ? sortDir === 'asc' ? 'ascending' : 'descending'
                    : col.sortable ? 'none' : undefined
                }
              >
                <span className="inline-flex items-center gap-1">
                  {col.header}
                  {col.sortable && sortKey === col.key && (
                    <span aria-hidden="true">{sortDir === 'asc' ? '▲' : '▼'}</span>
                  )}
                </span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {loading ? (
            <tr>
              <td
                colSpan={columns.length}
                className="h-24 text-center text-muted-foreground"
              >
                Loading…
              </td>
            </tr>
          ) : sortedData.length === 0 ? (
            <tr>
              <td
                colSpan={columns.length}
                className="h-24 text-center text-muted-foreground"
              >
                {emptyMessage}
              </td>
            </tr>
          ) : (
            sortedData.map((row) => (
              <tr
                key={keyExtractor(row)}
                className={cn(
                  'border-b border-border transition-colors hover:bg-surface',
                  onRowClick && 'cursor-pointer',
                )}
                onClick={onRowClick ? () => onRowClick(row) : undefined}
                tabIndex={onRowClick ? 0 : undefined}
                onKeyDown={
                  onRowClick
                    ? (e) => {
                        if (e.key === 'Enter' || e.key === ' ') {
                          e.preventDefault()
                          onRowClick(row)
                        }
                      }
                    : undefined
                }
                role={onRowClick ? 'button' : undefined}
              >
                {columns.map((col) => (
                  <td key={col.key} className={cn('p-3 align-middle', col.className)}>
                    {col.render
                      ? col.render(row)
                      : String((row as Record<string, unknown>)[sortKey === col.key ? col.key : col.key] ?? '')}
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  )
}

export const DataTable = React.forwardRef(DataTableInner) as <T>(
  props: DataTableProps<T> & { ref?: React.Ref<HTMLTableElement> },
) => React.ReactElement
