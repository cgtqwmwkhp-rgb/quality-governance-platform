import * as React from 'react'
import { cn } from '../../helpers/utils'

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
  }: DataTableProps<T>,
  ref: React.ForwardedRef<HTMLTableElement>,
) {
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
                  col.className,
                )}
                scope="col"
              >
                {col.header}
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
          ) : data.length === 0 ? (
            <tr>
              <td
                colSpan={columns.length}
                className="h-24 text-center text-muted-foreground"
              >
                {emptyMessage}
              </td>
            </tr>
          ) : (
            data.map((row) => (
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
                      : String((row as Record<string, unknown>)[col.key] ?? '')}
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
