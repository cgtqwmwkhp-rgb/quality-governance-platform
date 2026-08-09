/**
 * WD-1 filing wizard spine (prep scaffold).
 *
 * Steps live inside the existing Documents upload modal — never a second
 * Register or twin wizard app. Full L-18/18b/18c behaviour ships after WC-1 LIVE;
 * this module only defines the ordered phases and pure helpers.
 */

export const DOCUMENT_FILING_WIZARD_STEPS = [
  'file',
  'function',
  'related',
  'control',
] as const

export type DocumentFilingWizardStep = (typeof DOCUMENT_FILING_WIZARD_STEPS)[number]

export interface DocumentFunctionOption {
  id: number
  code: string
  name: string
  description?: string | null
  sort_order: number
  active: boolean
}

/** i18n keys for step chrome (titles stay short; bodies live on each step). */
export const DOCUMENT_FILING_STEP_TITLE_KEYS: Record<DocumentFilingWizardStep, string> = {
  file: 'documents.filing.step.file.title',
  function: 'documents.filing.step.function.title',
  related: 'documents.filing.step.related.title',
  control: 'documents.filing.step.control.title',
}

export const DOCUMENT_FILING_STEP_DESC_KEYS: Record<DocumentFilingWizardStep, string> = {
  file: 'documents.filing.step.file.description',
  function: 'documents.filing.step.function.description',
  related: 'documents.filing.step.related.description',
  control: 'documents.filing.step.control.description',
}

export function nextFilingWizardStep(
  step: DocumentFilingWizardStep,
): DocumentFilingWizardStep | null {
  const index = DOCUMENT_FILING_WIZARD_STEPS.indexOf(step)
  if (index < 0 || index >= DOCUMENT_FILING_WIZARD_STEPS.length - 1) return null
  return DOCUMENT_FILING_WIZARD_STEPS[index + 1]
}

export function filingWizardStepIndex(step: DocumentFilingWizardStep): number {
  return DOCUMENT_FILING_WIZARD_STEPS.indexOf(step)
}

/** Append optional WA-2 `function_code` only when the filer confirmed a code. */
export function appendOptionalFunctionCode(
  formData: FormData,
  functionCode: string | null | undefined,
): FormData {
  const code = typeof functionCode === 'string' ? functionCode.trim().toUpperCase() : ''
  if (code) {
    formData.append('function_code', code)
  }
  return formData
}

export function formatFunctionOptionLabel(fn: Pick<DocumentFunctionOption, 'code' | 'name'>): string {
  return `${fn.code} — ${fn.name}`
}
