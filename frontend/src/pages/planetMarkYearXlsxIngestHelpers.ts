/** PM-W1b — MS XLSX year carbon ingest helpers (Years tab). */

import type { PlanetMarkMsXlsxIngestResponse } from '../api/planetMarkClient'

export const PLANET_MARK_MS_XLSX_ACCEPT =
  '.xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'

export const PLANET_MARK_MS_XLSX_MAX_MB = 10

export function buildMsXlsxIngestFormData(file: File): FormData {
  const formData = new FormData()
  formData.append('file', file)
  return formData
}

export function validateMsXlsxFile(file: File): string | null {
  if (!file.name.toLowerCase().endsWith('.xlsx')) {
    return 'File must be an Excel workbook (.xlsx)'
  }
  if (file.size > PLANET_MARK_MS_XLSX_MAX_MB * 1024 * 1024) {
    return `File exceeds ${PLANET_MARK_MS_XLSX_MAX_MB} MB limit`
  }
  return null
}

export function inferYearLabelFromFilename(filename: string): string | null {
  const match = filename.match(/YE\d{4}/i)
  return match ? match[0].toUpperCase() : null
}

export function yearLabelMatchesWorkbook(
  yearLabel: string,
  filename: string,
): { ok: boolean; workbookYear: string | null } {
  const workbookYear = inferYearLabelFromFilename(filename)
  if (!workbookYear) {
    return { ok: true, workbookYear: null }
  }
  return {
    ok: workbookYear.toUpperCase() === yearLabel.toUpperCase(),
    workbookYear,
  }
}

export function formatIngestedTotals(result: PlanetMarkMsXlsxIngestResponse): {
  total: string
  perFte: string
  scope1: string
  scope2: string
  scope3: string
} {
  const fmt = (value: number | null | undefined, digits = 1) =>
    value != null && Number.isFinite(value) ? value.toFixed(digits) : '—'
  return {
    total: fmt(result.total_emissions),
    perFte: fmt(result.emissions_per_fte, 2),
    scope1: fmt(result.scope_1),
    scope2: fmt(result.scope_2_market),
    scope3: fmt(result.scope_3),
  }
}

export function isRetryableMsXlsxIngestError(error: unknown): boolean {
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
