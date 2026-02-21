import { cn } from '../../helpers/utils'

interface SkeletonProps {
  className?: string
  lines?: number
  variant?: 'text' | 'card' | 'table'
}

export function Skeleton({ className = '', lines = 3, variant = 'text' }: SkeletonProps) {
  if (variant === 'card') {
    return <CardSkeleton count={1} className={className} />
  }

  if (variant === 'table') {
    return <TableSkeleton className={className} />
  }

  return (
    <div className={cn('space-y-3', className)}>
      {Array.from({ length: lines }).map((_, i) => (
        <div
          key={i}
          className={cn(
            'h-4 rounded bg-muted animate-pulse',
            i === lines - 1 ? 'w-2/3' : 'w-full'
          )}
        />
      ))}
    </div>
  )
}

interface TableSkeletonProps {
  rows?: number
  columns?: number
  className?: string
}

export function TableSkeleton({ rows = 5, columns = 4, className = '' }: TableSkeletonProps) {
  return (
    <div className={cn('w-full', className)}>
      <div className="flex gap-4 mb-4 pb-3 border-b border-border">
        {Array.from({ length: columns }).map((_, i) => (
          <div
            key={i}
            className="h-4 rounded bg-muted animate-pulse flex-1"
          />
        ))}
      </div>
      <div className="space-y-3">
        {Array.from({ length: rows }).map((_, row) => (
          <div key={row} className="flex gap-4">
            {Array.from({ length: columns }).map((_, col) => (
              <div
                key={col}
                className={cn(
                  'h-4 rounded bg-muted/70 animate-pulse flex-1',
                  col === 0 && 'max-w-[140px]'
                )}
                style={{ animationDelay: `${(row * columns + col) * 50}ms` }}
              />
            ))}
          </div>
        ))}
      </div>
    </div>
  )
}

interface CardSkeletonProps {
  count?: number
  className?: string
}

export function CardSkeleton({ count = 3, className = '' }: CardSkeletonProps) {
  return (
    <div className={cn('grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4', className)}>
      {Array.from({ length: count }).map((_, i) => (
        <div
          key={i}
          className="rounded-xl border border-border bg-card p-6 space-y-4"
          style={{ animationDelay: `${i * 100}ms` }}
        >
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-muted animate-pulse" />
            <div className="flex-1 space-y-2">
              <div className="h-4 w-3/4 rounded bg-muted animate-pulse" />
              <div className="h-3 w-1/2 rounded bg-muted/70 animate-pulse" />
            </div>
          </div>
          <div className="space-y-2">
            <div className="h-3 w-full rounded bg-muted/60 animate-pulse" />
            <div className="h-3 w-5/6 rounded bg-muted/60 animate-pulse" />
          </div>
          <div className="flex gap-2 pt-2">
            <div className="h-6 w-16 rounded-full bg-muted animate-pulse" />
            <div className="h-6 w-20 rounded-full bg-muted animate-pulse" />
          </div>
        </div>
      ))}
    </div>
  )
}
