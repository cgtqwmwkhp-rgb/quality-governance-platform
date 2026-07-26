import { useCallback, useMemo, useRef, useState } from 'react'
import {
  focusInvalidControl,
  validateFields,
  type FieldSpecs,
  type ValidationOutcome,
} from './formValidation'

export interface UseFormControllerOptions<TKeys extends string> {
  /**
   * Field rules in the order the controls appear on screen. Declaration order
   * decides which control we scroll and focus to when several are invalid.
   */
  fields: FieldSpecs<TKeys>
  /** Current form values, keyed by the same names as `fields`. */
  values: Record<string, unknown>
  /** Maps a field name to the DOM id of its control. */
  controlId: (name: TKeys) => string
  /** Called only when validation passes. Throwing produces a persistent error. */
  onSubmit: (values: Record<string, unknown>) => void | Promise<void>
  /** Turns a thrown error into the persistent message shown to the user. */
  toErrorMessage?: (error: unknown) => string
}

export interface FormFieldBinding {
  id: string
  label: string
  required: boolean
  error: string | null
}

export interface FormController<TKeys extends string> {
  errors: Partial<Record<TKeys, string>>
  submitting: boolean
  /** Persistent failure message. Cleared only by another submit or `resetFeedback`. */
  submitError: string | null
  setSubmitError: (message: string | null) => void
  resetFeedback: () => void
  /** Spread onto `<form>`: wires submit and disables the browser's own bubbles. */
  formProps: { onSubmit: (event: { preventDefault: () => void }) => void; noValidate: true }
  /** Spread onto `<FormField>`: id, label, required and error from one source. */
  fieldProps: (name: TKeys) => FormFieldBinding
  /** Escape hatch for callers that need the raw outcome (e.g. gating a CTA). */
  validateNow: () => ValidationOutcome<TKeys>
}

function defaultToErrorMessage(error: unknown): string {
  return error instanceof Error && error.message ? error.message : 'Something went wrong'
}

/**
 * Shared submit + validation controller behind every adopted form.
 *
 * Responsibilities, all of which were previously re-implemented (or missed) per
 * page: required-field marking driven from one source, inline errors that name
 * the field, moving the user to the first invalid control, a submit that cannot
 * be double-fired, and a failure message that persists instead of a toast.
 */
export function useFormController<TKeys extends string>({
  fields,
  values,
  controlId,
  onSubmit,
  toErrorMessage = defaultToErrorMessage,
}: UseFormControllerOptions<TKeys>): FormController<TKeys> {
  const [showErrorsFor, setShowErrorsFor] = useState<ReadonlySet<string>>(() => new Set())
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)
  const submittingRef = useRef(false)

  // Re-derived every render so an error disappears as soon as the user fixes
  // the field, rather than lingering until the next submit attempt.
  const outcome = useMemo(() => validateFields(fields, values), [fields, values])

  const errors = useMemo(() => {
    const visible: Partial<Record<TKeys, string>> = {}
    for (const name of Object.keys(outcome.errors) as TKeys[]) {
      if (showErrorsFor.has(name)) visible[name] = outcome.errors[name]
    }
    return visible
  }, [outcome, showErrorsFor])

  const resetFeedback = useCallback(() => {
    setShowErrorsFor(new Set())
    setSubmitError(null)
  }, [])

  const handleSubmit = useCallback(
    (event: { preventDefault: () => void }) => {
      event.preventDefault()
      // Guards Enter-key submits racing the disabled button within one tick.
      if (submittingRef.current) return
      setSubmitError(null)

      const result = validateFields(fields, values)
      if (!result.valid) {
        setShowErrorsFor(new Set(Object.keys(result.errors)))
        if (result.firstInvalidField) {
          // The control already exists in the DOM, so this does not need to wait
          // for the error text to render; `role="alert"` announces that separately.
          focusInvalidControl(controlId(result.firstInvalidField))
        }
        return
      }

      setShowErrorsFor(new Set())
      submittingRef.current = true
      setSubmitting(true)
      void (async () => {
        try {
          await onSubmit(values)
        } catch (error) {
          setSubmitError(toErrorMessage(error))
        } finally {
          submittingRef.current = false
          setSubmitting(false)
        }
      })()
    },
    [fields, values, controlId, onSubmit, toErrorMessage],
  )

  const fieldProps = useCallback(
    (name: TKeys): FormFieldBinding => ({
      id: controlId(name),
      label: fields[name].label,
      required: Boolean(fields[name].required),
      error: errors[name] ?? null,
    }),
    [controlId, fields, errors],
  )

  const validateNow = useCallback(() => validateFields(fields, values), [fields, values])

  return {
    errors,
    submitting,
    submitError,
    setSubmitError,
    resetFeedback,
    formProps: { onSubmit: handleSubmit, noValidate: true },
    fieldProps,
    validateNow,
  }
}
