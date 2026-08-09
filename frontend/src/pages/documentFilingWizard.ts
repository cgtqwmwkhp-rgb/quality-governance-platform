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

/**
 * NS-1 cascade levels. The level is the first digit of the PEL sequence
 * (`PEL-HSEQ-3001` is a level-3 Procedure), so it is picked at filing and
 * cannot be changed afterwards without reissuing the reference.
 */
export const CASCADE_LEVELS = [1, 2, 3, 4, 5] as const

export type CascadeLevel = (typeof CASCADE_LEVELS)[number]

export interface CascadeLevelOption {
  level: CascadeLevel
  /** Short code shown alongside the name, e.g. `L3`. */
  code: string
  name: string
}

export const CASCADE_LEVEL_OPTIONS: readonly CascadeLevelOption[] = [
  { level: 1, code: 'L1', name: 'Manual' },
  { level: 2, code: 'L2', name: 'Policy' },
  { level: 3, code: 'L3', name: 'Procedure or Standard' },
  { level: 4, code: 'L4', name: 'SOP, RAMS or Assessment' },
  { level: 5, code: 'L5', name: 'Form, Register or Record' },
] as const

export function isCascadeLevel(value: unknown): value is CascadeLevel {
  return typeof value === 'number' && (CASCADE_LEVELS as readonly number[]).includes(value)
}

export function formatCascadeLevelLabel(option: CascadeLevelOption): string {
  return `${option.code} — ${option.name}`
}

/** Render a level for the Register/detail chrome; blank when the document has none. */
export function formatCascadeLevelBadge(level: number | null | undefined): string {
  return isCascadeLevel(level) ? `L${level}` : ''
}

/**
 * Append NS-1 `cascade_level` when the filer picked one.
 *
 * The server refuses `function_code` without a level, so this is only ever
 * "optional" in the sense that a document may be filed with neither.
 */
export function appendOptionalCascadeLevel(
  formData: FormData,
  cascadeLevel: number | null | undefined,
): FormData {
  if (isCascadeLevel(cascadeLevel)) {
    formData.append('cascade_level', String(cascadeLevel))
  }
  return formData
}

/**
 * Can the filer submit this Function step?
 *
 * Confirming a function means allocating an immutable banded PEL reference, so
 * a level is required with it. Filing with neither is still allowed — the
 * document just gets no PEL reference. Mirrors the server rule in
 * `upload_document` so the UI never submits a request that is certain to 400.
 */
export function canConfirmFilingStep(
  functionCode: string | null | undefined,
  cascadeLevel: number | null | undefined,
): boolean {
  const code = typeof functionCode === 'string' ? functionCode.trim() : ''
  if (!code) return true
  return isCascadeLevel(cascadeLevel)
}
