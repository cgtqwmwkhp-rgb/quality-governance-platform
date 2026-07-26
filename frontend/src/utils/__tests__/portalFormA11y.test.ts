import { describe, expect, it } from 'vitest'
import {
  portalAriaRequired,
  portalFieldId,
  portalRequiredProps,
  portalStripRequiredMarker,
} from '../portalFormA11y'

describe('portalFormA11y', () => {
  it('portalFieldId namespaces portal controls', () => {
    expect(portalFieldId('person_role')).toBe('portal-field-person_role')
  })

  it('portalRequiredProps keeps required and aria-required in sync', () => {
    expect(portalRequiredProps(true)).toEqual({ required: true, 'aria-required': 'true' })
    expect(portalRequiredProps(false)).toEqual({})
  })

  it('portalAriaRequired omits DOM required for custom controls', () => {
    expect(portalAriaRequired(true)).toEqual({ 'aria-required': 'true' })
    expect(portalAriaRequired(false)).toEqual({})
  })

  it('portalStripRequiredMarker removes trailing asterisks (PX-159)', () => {
    expect(portalStripRequiredMarker('Customer / Site *')).toBe('Customer / Site')
    expect(portalStripRequiredMarker('Customer / Site **')).toBe('Customer / Site')
    expect(portalStripRequiredMarker('Customer / Site')).toBe('Customer / Site')
  })
})
