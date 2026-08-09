import { describe, expect, it } from 'vitest'
import {
  appendOptionalFunctionCode,
  DOCUMENT_FILING_WIZARD_STEPS,
  filingWizardStepIndex,
  formatFunctionOptionLabel,
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
