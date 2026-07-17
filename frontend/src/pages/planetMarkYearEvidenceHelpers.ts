import type { PlanetMarkEvidenceRecord } from '../api/planetMarkClient'

export const PLANET_MARK_YEAR_CERT_DOC_TYPES = {
  measurementReport: 'measurement_report',
  certificate: 'planet_mark_certificate',
} as const

export type PlanetMarkYearCertDocType =
  (typeof PLANET_MARK_YEAR_CERT_DOC_TYPES)[keyof typeof PLANET_MARK_YEAR_CERT_DOC_TYPES]

export const PLANET_MARK_YEAR_EVIDENCE_ACCEPT = '.pdf,.jpg,.jpeg,.png,.webp,.xls,.xlsx,.csv'

export const PLANET_MARK_YEAR_EVIDENCE_MAX_MB = 20

const ALLOWED_MIME_TYPES = new Set([
  'application/pdf',
  'image/jpeg',
  'image/png',
  'image/webp',
  'application/vnd.ms-excel',
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  'text/csv',
])

export function isPlanetMarkYearCertDocType(
  documentType: string,
): documentType is PlanetMarkYearCertDocType {
  return (
    documentType === PLANET_MARK_YEAR_CERT_DOC_TYPES.measurementReport ||
    documentType === PLANET_MARK_YEAR_CERT_DOC_TYPES.certificate
  )
}

export function filterYearReportEvidence(
  evidence: PlanetMarkEvidenceRecord[],
): PlanetMarkEvidenceRecord[] {
  return evidence.filter((item) => isPlanetMarkYearCertDocType(item.document_type))
}

export function buildYearEvidenceUploadFormData(file: File, documentType: PlanetMarkYearCertDocType): FormData {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('document_name', file.name)
  formData.append('document_type', documentType)
  formData.append('evidence_category', 'certification')
  return formData
}

export function validateYearEvidenceFile(file: File): string | null {
  if (file.size > PLANET_MARK_YEAR_EVIDENCE_MAX_MB * 1024 * 1024) {
    return `File exceeds ${PLANET_MARK_YEAR_EVIDENCE_MAX_MB} MB limit`
  }
  if (file.type && !ALLOWED_MIME_TYPES.has(file.type)) {
    return 'File type not supported. Please use PDF, image, Excel or CSV.'
  }
  return null
}

export function formatEvidenceFileSizeKb(sizeKb: number | null | undefined): string {
  if (sizeKb == null || !Number.isFinite(sizeKb) || sizeKb <= 0) return '—'
  if (sizeKb >= 1024) return `${(sizeKb / 1024).toFixed(1)} MB`
  return `${Math.round(sizeKb)} KB`
}

export function formatEvidenceUploadedAt(uploadedAt: string | null | undefined): string {
  if (!uploadedAt) return '—'
  const parsed = new Date(uploadedAt)
  if (Number.isNaN(parsed.getTime())) return uploadedAt
  return parsed.toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function yearEvidenceDocumentTypeLabelKey(documentType: string): string {
  if (documentType === PLANET_MARK_YEAR_CERT_DOC_TYPES.measurementReport) {
    return 'planet_mark.shell.years.evidence.type.measurement_report'
  }
  if (documentType === PLANET_MARK_YEAR_CERT_DOC_TYPES.certificate) {
    return 'planet_mark.shell.years.evidence.type.planet_mark_certificate'
  }
  return 'planet_mark.shell.years.evidence.type.other'
}

export function isRetryableYearEvidenceError(error: unknown): boolean {
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

/** True when the evidence row has a real blob (downloadable). */
export function evidenceHasStorageKey(storageKey: string | null | undefined): boolean {
  return Boolean(storageKey && String(storageKey).trim().length > 0)
}

export function latestEvidenceIdForType(
  evidence: PlanetMarkEvidenceRecord[],
  documentType: PlanetMarkYearCertDocType,
): number | null {
  const match = evidence
    .filter((item) => item.document_type === documentType && evidenceHasStorageKey(item.storage_key))
    .sort(
      (a, b) => new Date(b.uploaded_at).getTime() - new Date(a.uploaded_at).getTime(),
    )[0]
  return match?.id ?? null
}
