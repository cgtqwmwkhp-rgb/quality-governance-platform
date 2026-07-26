/**
 * Shared accessibility helpers for portal intake forms.
 *
 * Keeps programmatic `required` / `aria-required` in sync with the visual
 * asterisk — the gap called out in PX-301.
 */

export function portalFieldId(fieldName: string): string {
  return `portal-field-${fieldName}`
}

/**
 * Strip a trailing required marker from a label when the control already
 * renders its own asterisk (PX-159 — "Customer / Site **").
 */
export function portalStripRequiredMarker(label: string): string {
  return label.replace(/\s*\*+\s*$/u, '').trimEnd()
}

/** Props for native input/select/textarea controls. */
export function portalRequiredProps(required: boolean): {
  required?: true
  'aria-required'?: 'true'
} {
  return required ? { required: true, 'aria-required': 'true' as const } : {}
}

/** Props for custom controls (buttons acting as selects) that cannot take `required`. */
export function portalAriaRequired(required: boolean): { 'aria-required'?: 'true' } {
  return required ? { 'aria-required': 'true' as const } : {}
}
