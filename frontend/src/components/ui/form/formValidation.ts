/**
 * Pure validation core for the shared form primitive.
 *
 * Kept free of React so the rules that decide "is this field required" and
 * "which control do we send the user to" are unit-testable on their own and
 * cannot drift from the rendered asterisk / `required` attribute.
 */

/** A value the user has not supplied. `false` is a legitimate answer, not a blank. */
export function isBlankValue(value: unknown): boolean {
  if (value === null || value === undefined) return true
  if (typeof value === 'string') return value.trim() === ''
  if (Array.isArray(value)) return value.length === 0
  return false
}

export interface FieldSpec {
  /**
   * Human label for the field. Drives the visible `<label>`, the asterisk and
   * the default error text, so the message always names the offending field.
   */
  label: string
  /** Marks the field visually (asterisk) *and* programmatically (`required`/`aria-required`). */
  required?: boolean
  /** Overrides the generated "<label> is required" copy. */
  requiredMessage?: string
  /** Additional rule. Return an error string, or `null` when the value is acceptable. */
  validate?: (value: unknown, values: Record<string, unknown>) => string | null
}

export type FieldSpecs<TKeys extends string = string> = Record<TKeys, FieldSpec>

export interface ValidationOutcome<TKeys extends string = string> {
  valid: boolean
  errors: Partial<Record<TKeys, string>>
  /** First failing field in *declaration* order — where focus and scroll should land. */
  firstInvalidField: TKeys | null
}

export function defaultRequiredMessage(label: string): string {
  return `${label} is required`
}

/**
 * Validate `values` against `specs`.
 *
 * Field order is the declaration order of `specs`, which is why callers should
 * declare specs in the order the controls appear on screen: `firstInvalidField`
 * is what we scroll and focus to.
 */
export function validateFields<TKeys extends string>(
  specs: FieldSpecs<TKeys>,
  values: Record<string, unknown>,
): ValidationOutcome<TKeys> {
  const errors: Partial<Record<TKeys, string>> = {}
  let firstInvalidField: TKeys | null = null

  for (const name of Object.keys(specs) as TKeys[]) {
    const spec = specs[name]
    if (!spec) continue
    const value = values[name]

    let message: string | null = null
    if (spec.required && isBlankValue(value)) {
      message = spec.requiredMessage || defaultRequiredMessage(spec.label)
    } else if (spec.validate) {
      message = spec.validate(value, values)
    }

    if (message) {
      errors[name] = message
      if (firstInvalidField === null) firstInvalidField = name
    }
  }

  return { valid: firstInvalidField === null, errors, firstInvalidField }
}

/** DOM ids derived from one place so label/control/error/description always agree. */
export function fieldErrorId(controlId: string): string {
  return `${controlId}-error`
}

export function fieldHintId(controlId: string): string {
  return `${controlId}-hint`
}

/**
 * Move the user to the offending control: scroll it into view, then focus it.
 *
 * Long dialogs scroll, so an error rendered at the foot of the form is invisible
 * from the control that caused it (PX-261) — and an error rendered at the head of
 * the form is invisible from the footer button (PX-291). Both are fixed by moving
 * the user rather than by choosing a better place for the message.
 */
export function focusInvalidControl(controlId: string, doc: Document = document): boolean {
  const el = doc.getElementById(controlId)
  if (!el) return false
  if (typeof el.scrollIntoView === 'function') {
    el.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }
  if (typeof (el as HTMLElement).focus === 'function') {
    ;(el as HTMLElement).focus({ preventScroll: true })
  }
  return true
}
