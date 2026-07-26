import * as React from 'react'
import { AlertCircle } from 'lucide-react'
import { Label } from '../Label'
import { cn } from '../../../helpers/utils'
import { fieldErrorId, fieldHintId } from './formValidation'

/**
 * Props handed to the control. `required` is only present for native form
 * controls — putting it on a `<button>` (a Radix `SelectTrigger`) would be
 * invalid HTML, so custom controls get the ARIA equivalent only.
 */
export interface FormControlProps {
  id: string
  required?: boolean
  'aria-required'?: 'true'
  'aria-invalid'?: 'true'
  'aria-describedby'?: string
}

export interface FormFieldProps {
  /** DOM id of the control. Also derives the label `htmlFor` and the error/hint ids. */
  id: string
  label: React.ReactNode
  /**
   * Single source of truth for "this field is mandatory": renders the asterisk
   * *and* emits `required` / `aria-required` on the control. The two can never
   * disagree because they are the same prop.
   */
  required?: boolean
  error?: string | null
  hint?: React.ReactNode
  /**
   * Set `false` for controls that are not native `input`/`select`/`textarea`
   * (e.g. a Radix `SelectTrigger`), which cannot carry a `required` attribute.
   */
  nativeControl?: boolean
  className?: string
  labelClassName?: string
  children: (control: FormControlProps) => React.ReactNode
}

/**
 * Label + control + inline, field-adjacent error, wired together for assistive
 * technology.
 *
 * Promoted from the External Audit Intake dialog, which was the only form in the
 * product that showed a clear validation message. That pattern put the message at
 * the foot of the form; here it sits next to the control it is about.
 */
export function FormField({
  id,
  label,
  required = false,
  error,
  hint,
  nativeControl = true,
  className,
  labelClassName,
  children,
}: FormFieldProps) {
  const errorId = fieldErrorId(id)
  const hintId = fieldHintId(id)
  const describedBy = [hint ? hintId : null, error ? errorId : null].filter(Boolean).join(' ')

  const control: FormControlProps = {
    id,
    ...(nativeControl && required ? { required: true } : {}),
    ...(required ? { 'aria-required': 'true' as const } : {}),
    ...(error ? { 'aria-invalid': 'true' as const } : {}),
    ...(describedBy ? { 'aria-describedby': describedBy } : {}),
  }

  return (
    <div className={cn('space-y-1.5', className)}>
      <Label
        htmlFor={id}
        required={required}
        className={cn('block text-sm font-medium text-foreground', labelClassName)}
      >
        {label}
      </Label>
      {children(control)}
      {hint ? (
        <p id={hintId} className="text-xs text-muted-foreground">
          {hint}
        </p>
      ) : null}
      {error ? (
        <p
          id={errorId}
          role="alert"
          data-testid={`${id}-error`}
          className="flex items-start gap-1.5 text-sm text-destructive"
        >
          <AlertCircle className="mt-0.5 h-4 w-4 flex-shrink-0" aria-hidden="true" />
          <span>{error}</span>
        </p>
      ) : null}
    </div>
  )
}
