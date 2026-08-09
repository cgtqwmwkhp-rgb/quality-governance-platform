import { describe, expect, it } from 'vitest'
import {
  appendOptionalCascadeLevel,
  appendOptionalFunctionCode,
  canConfirmFilingStep,
  CASCADE_LEVEL_OPTIONS,
  DOCUMENT_FILING_WIZARD_STEPS,
  filingWizardStepIndex,
  formatCascadeLevelBadge,
  formatCascadeLevelLabel,
  formatFunctionOptionLabel,
  isCascadeLevel,
  nextFilingWizardStep,
} from '../documentFilingWizard'

describe('documentFilingWizard', () => {
  it('orders File → Function → Related → Control', () => {
    expect([...DOCUMENT_FILING_WIZARD_STEPS]).toEqual(['file', 'function', 'related', 'control'])
    expect(filingWizardStepIndex('function')).toBe(1)
    expect(nextFilingWizardStep('file')).toBe('function')
    expect(nextFilingWizardStep('function')).toBe('related')
    expect(nextFilingWizardStep('related')).toBe('control')
    expect(nextFilingWizardStep('control')).toBeNull()
  })

  it('appends function_code only when a non-empty code is confirmed', () => {
    const withCode = appendOptionalFunctionCode(new FormData(), '  hseq ')
    expect(withCode.get('function_code')).toBe('HSEQ')

    const skipped = appendOptionalFunctionCode(new FormData(), null)
    expect(skipped.get('function_code')).toBeNull()

    const blank = appendOptionalFunctionCode(new FormData(), '   ')
    expect(blank.get('function_code')).toBeNull()
  })

  it('formats function picker labels as CODE — name', () => {
    expect(formatFunctionOptionLabel({ code: 'IT', name: 'Information Technology' })).toBe(
      'IT — Information Technology',
    )
  })
})

describe('documentFilingWizard cascade level (NS-1)', () => {
  it('offers exactly the five Northern Star v6 levels in cascade order', () => {
    expect(CASCADE_LEVEL_OPTIONS.map((o) => o.level)).toEqual([1, 2, 3, 4, 5])
    expect(CASCADE_LEVEL_OPTIONS.map((o) => o.name)).toEqual([
      'Manual',
      'Policy',
      'Procedure or Standard',
      'SOP, RAMS or Assessment',
      'Form, Register or Record',
    ])
  })

  it('accepts only 1-5 as a cascade level', () => {
    expect([1, 2, 3, 4, 5].every(isCascadeLevel)).toBe(true)
    for (const bad of [0, 6, -1, 2.5, '3', null, undefined, NaN]) {
      expect(isCascadeLevel(bad)).toBe(false)
    }
  })

  it('appends cascade_level only when a valid level is chosen', () => {
    expect(appendOptionalCascadeLevel(new FormData(), 3).get('cascade_level')).toBe('3')
    expect(appendOptionalCascadeLevel(new FormData(), null).get('cascade_level')).toBeNull()
    expect(appendOptionalCascadeLevel(new FormData(), 0).get('cascade_level')).toBeNull()
    expect(appendOptionalCascadeLevel(new FormData(), 6).get('cascade_level')).toBeNull()
  })

  it('requires a level when a function is confirmed, and only then', () => {
    // Confirming a function allocates an immutable banded reference.
    expect(canConfirmFilingStep('HSEQ', null)).toBe(false)
    expect(canConfirmFilingStep('HSEQ', 3)).toBe(true)
    // Filing with neither is still allowed — no PEL reference is issued.
    expect(canConfirmFilingStep(null, null)).toBe(true)
    expect(canConfirmFilingStep('  ', null)).toBe(true)
    // An out-of-range level is not a level.
    expect(canConfirmFilingStep('HSEQ', 6)).toBe(false)
  })

  it('labels levels for the picker and badges them for the register', () => {
    expect(formatCascadeLevelLabel(CASCADE_LEVEL_OPTIONS[2])).toBe('L3 — Procedure or Standard')
    expect(formatCascadeLevelBadge(3)).toBe('L3')
    expect(formatCascadeLevelBadge(null)).toBe('')
    expect(formatCascadeLevelBadge(9)).toBe('')
  })
})
