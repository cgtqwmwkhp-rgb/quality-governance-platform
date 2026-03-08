import { Link, useLocation } from 'react-router-dom'
import { ChevronRight, Home } from 'lucide-react'
import { cn } from '../../helpers/utils'

export interface BreadcrumbItem {
  label: string
  href?: string
}

interface BreadcrumbsProps {
  items: BreadcrumbItem[]
  className?: string
}

export function Breadcrumbs({ items, className }: BreadcrumbsProps) {
  const location = useLocation()

  return (
    <nav
      aria-label="Breadcrumb"
      className={cn('flex items-center gap-1 text-sm text-muted-foreground mb-4', className)}
    >
      <Link
        to="/"
        className="flex items-center gap-1 hover:text-foreground transition-colors"
        aria-label="Home"
      >
        <Home className="w-4 h-4" />
      </Link>

      {items.map((item, idx) => {
        const isLast = idx === items.length - 1
        const isActive = item.href === location.pathname

        return (
          <span key={idx} className="flex items-center gap-1">
            <ChevronRight className="w-3.5 h-3.5 text-muted-foreground/60" aria-hidden />
            {isLast || !item.href ? (
              <span
                className={cn('font-medium', isLast && 'text-foreground')}
                aria-current={isLast ? 'page' : undefined}
              >
                {item.label}
              </span>
            ) : (
              <Link
                to={item.href}
                className={cn(
                  'hover:text-foreground transition-colors',
                  isActive && 'text-foreground font-medium',
                )}
              >
                {item.label}
              </Link>
            )}
          </span>
        )
      })}
    </nav>
  )
}
