import { Link } from 'react-router-dom'
import { cn } from '../../helpers/utils'

/**
 * Real reference anchor for case-register rows (PX-200 / PX-173).
 *
 * Registers used to style the reference as if it were a link (`text-primary`)
 * while the open path was only `navigate()` on a `<tr role="button">`. That
 * blocked middle-click / open-in-new-tab / copy-link, and announced the whole
 * row as a button even when only the reference looked activatable.
 *
 * Clicks on the link stop row bubbling so React Router handles navigation once.
 */
export function CaseRegisterReferenceLink({
  to,
  children,
  className,
  'aria-label': ariaLabel,
}: {
  to: string
  children: React.ReactNode
  className?: string
  'aria-label'?: string
}) {
  return (
    <Link
      to={to}
      className={cn('font-mono text-sm text-primary hover:underline focus-visible:underline', className)}
      aria-label={ariaLabel}
      onClick={(event) => event.stopPropagation()}
    >
      {children}
    </Link>
  )
}
