import * as React from 'react'
import { Loader2 } from 'lucide-react'
import { Button, type ButtonProps } from '../Button'

export interface SubmitButtonProps extends Omit<ButtonProps, 'type' | 'children'> {
  submitting: boolean
  /** Label shown while the request is in flight, e.g. "Creating…". */
  submittingLabel: string
  children: React.ReactNode
  'data-testid'?: string
}

/**
 * Submit control that cannot be double-fired while a request is in flight.
 *
 * A slow submit with no visible change invites a second click, which on a
 * register with no delete path means a duplicate record (PX-204). The button is
 * disabled, shows a spinner and swaps its label, and the state change is
 * announced for assistive technology.
 */
export function SubmitButton({
  submitting,
  submittingLabel,
  children,
  disabled,
  'data-testid': testId,
  ...props
}: SubmitButtonProps) {
  return (
    <>
      <Button
        type="submit"
        disabled={submitting || disabled}
        aria-busy={submitting || undefined}
        data-testid={testId ?? 'form-submit'}
        {...props}
      >
        {submitting ? (
          <>
            <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
            {submittingLabel}
          </>
        ) : (
          children
        )}
      </Button>
      <span className="sr-only" role="status" aria-live="polite">
        {submitting ? submittingLabel : ''}
      </span>
    </>
  )
}
