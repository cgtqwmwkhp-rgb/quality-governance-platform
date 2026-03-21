import { ReactNode } from 'react'

export interface CaseSummaryRailItem {
  label: string
  value: string
  icon?: ReactNode
}

interface CaseSummaryRailProps {
  items: CaseSummaryRailItem[]
}

export function CaseSummaryRail({ items }: CaseSummaryRailProps) {
  const visibleItems = items.filter((item) => item.value && item.value !== 'Not provided')

  if (visibleItems.length === 0) {
    return null
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-3">
      {visibleItems.map((item) => (
        <div
          key={item.label}
          className="rounded-xl border border-border bg-card px-4 py-3 flex items-start gap-3"
        >
          {item.icon ? (
            <div className="w-9 h-9 rounded-lg bg-primary/10 text-primary flex items-center justify-center shrink-0">
              {item.icon}
            </div>
          ) : null}
          <div className="min-w-0">
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              {item.label}
            </p>
            <p className="text-sm font-medium text-foreground mt-1 break-words">{item.value}</p>
          </div>
        </div>
      ))}
    </div>
  )
}
