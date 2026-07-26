import * as React from 'react'
import { AlertCircle, CheckCircle2, CloudOff, Info } from 'lucide-react'
import { cn } from '../../../helpers/utils'

export type FormNoticeTone = 'error' | 'warning' | 'success' | 'info'

const toneStyles: Record<FormNoticeTone, string> = {
  error: 'bg-destructive/10 border-destructive/30 text-destructive',
  warning:
    'border-amber-300 bg-amber-50 text-amber-950 dark:border-amber-700 dark:bg-amber-950/30 dark:text-amber-100',
  success: 'bg-success/10 border-success/30 text-success',
  info: 'bg-primary/5 border-primary/20 text-foreground',
}

const toneIcons: Record<FormNoticeTone, React.ElementType> = {
  error: AlertCircle,
  warning: CloudOff,
  success: CheckCircle2,
  info: Info,
}

export interface FormNoticeProps {
  tone?: FormNoticeTone
  title?: React.ReactNode
  children: React.ReactNode
  id?: string
  className?: string
  'data-testid'?: string
  /** Action rendered under the message (e.g. "Retry", "Open existing record"). */
  action?: React.ReactNode
}

/**
 * Persistent, in-page outcome message for a form.
 *
 * Deliberately *not* a toast: a toast auto-dismisses, so ten seconds after a
 * failed save there is nothing left on the page to tell the user the save failed
 * (PX-208), and an offline save looks exactly like a successful one (PX-127).
 * This block stays until the component clears it.
 */
export function FormNotice({
  tone = 'error',
  title,
  children,
  id,
  className,
  action,
  'data-testid': testId,
}: FormNoticeProps) {
  const Icon = toneIcons[tone]
  return (
    <div
      id={id}
      role={tone === 'error' ? 'alert' : 'status'}
      aria-live={tone === 'error' ? 'assertive' : 'polite'}
      data-testid={testId ?? 'form-notice'}
      data-tone={tone}
      className={cn('flex items-start gap-2 rounded-xl border p-3', toneStyles[tone], className)}
    >
      <Icon className="mt-0.5 h-5 w-5 flex-shrink-0" aria-hidden="true" />
      <div className="min-w-0 flex-1 text-sm">
        {title ? <p className="font-semibold">{title}</p> : null}
        <div className={cn(title && 'mt-1')}>{children}</div>
        {action ? <div className="mt-2">{action}</div> : null}
      </div>
    </div>
  )
}
