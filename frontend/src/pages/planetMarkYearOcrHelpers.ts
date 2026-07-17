/** PM OCR year-readings helpers — extract preview → apply honesty. */

export interface PlanetMarkOcrField {
  value: string | null
  confidence: string
  raw_snippet: string | null
}

export interface PlanetMarkOcrExtractResponse {
  source_filename: string
  document_kind: string
  extraction_method: string
  total_co2e_tonnes: PlanetMarkOcrField
  co2e_per_fte: PlanetMarkOcrField
  average_fte: PlanetMarkOcrField
  certificate_number: PlanetMarkOcrField
  reporting_period_label: PlanetMarkOcrField
  certification_status_cue: PlanetMarkOcrField
  warnings: string[]
  text_excerpt: string
  year_label: string
  xlsx_ingested: boolean
  period_mismatch_warning: string | null
  evidence_id: number | null
}

export interface PlanetMarkOcrApplyFieldResult {
  field: string
  action: string
  value: string | null
  reason: string | null
}

export interface PlanetMarkOcrApplyResponse {
  year_id: number
  year_label: string
  applied: PlanetMarkOcrApplyFieldResult[]
  skipped: PlanetMarkOcrApplyFieldResult[]
  message: string
  updated: {
    total_emissions: number | null
    average_fte: number | null
    emissions_per_fte: number | null
    certificate_number: string | null
  }
}

export type OcrPreviewFieldKey =
  | 'total_co2e_tonnes'
  | 'co2e_per_fte'
  | 'average_fte'
  | 'certificate_number'
  | 'reporting_period_label'
  | 'certification_status_cue'

export const OCR_PREVIEW_FIELD_KEYS: OcrPreviewFieldKey[] = [
  'total_co2e_tonnes',
  'co2e_per_fte',
  'average_fte',
  'certificate_number',
  'reporting_period_label',
  'certification_status_cue',
]

export function isExtractedField(field: PlanetMarkOcrField | null | undefined): boolean {
  return Boolean(field?.value != null && field.confidence !== 'none')
}

export function formatOcrFieldDisplay(field: PlanetMarkOcrField | null | undefined): string {
  if (!field || !isExtractedField(field)) return '—'
  return String(field.value)
}

export function ocrFieldLabelKey(field: OcrPreviewFieldKey): string {
  return `planet_mark.shell.years.ocr.field.${field}`
}

export function canApplyOcrPreview(preview: PlanetMarkOcrExtractResponse | null): boolean {
  if (!preview) return false
  return (
    isExtractedField(preview.total_co2e_tonnes) ||
    isExtractedField(preview.co2e_per_fte) ||
    isExtractedField(preview.average_fte) ||
    isExtractedField(preview.certificate_number)
  )
}

export function needsXlsxOverwriteConfirmation(preview: PlanetMarkOcrExtractResponse | null): boolean {
  if (!preview?.xlsx_ingested) return false
  return (
    isExtractedField(preview.total_co2e_tonnes) ||
    isExtractedField(preview.co2e_per_fte) ||
    isExtractedField(preview.average_fte)
  )
}

export function evidenceHasDownloadableStorage(
  storageKey: string | null | undefined,
): boolean {
  return Boolean(storageKey && storageKey.trim().length > 0)
}

export function isRetryableOcrError(error: unknown): boolean {
  if (!error || typeof error !== 'object') return false
  const axiosLike = error as {
    code?: string
    message?: string
    response?: { status?: number }
  }
  if (axiosLike.code === 'ECONNABORTED' || axiosLike.message?.includes('timeout')) {
    return true
  }
  const status = axiosLike.response?.status
  return status === 502 || status === 503 || status === 504
}
