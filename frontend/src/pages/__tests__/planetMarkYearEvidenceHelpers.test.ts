import { describe, expect, it } from 'vitest'
import type { PlanetMarkEvidenceRecord } from '../../api/planetMarkClient'
import {
  PLANET_MARK_YEAR_CERT_DOC_TYPES,
  buildYearEvidenceUploadFormData,
  filterYearReportEvidence,
  formatEvidenceFileSizeKb,
  isPlanetMarkYearCertDocType,
  isRetryableYearEvidenceError,
  validateYearEvidenceFile,
  yearEvidenceDocumentTypeLabelKey,
} from '../planetMarkYearEvidenceHelpers'

function evidence(overrides: Partial<PlanetMarkEvidenceRecord> = {}): PlanetMarkEvidenceRecord {
  return {
    id: 1,
    document_name: 'report.pdf',
    document_type: 'measurement_report',
    evidence_category: 'certification',
    period_covered: null,
    file_size_kb: 512,
    mime_type: 'application/pdf',
    is_verified: false,
    verified_by: null,
    linked_action_id: null,
    notes: null,
    uploaded_by: 'user',
    uploaded_at: '2026-01-15T10:00:00Z',
    storage_key: 'key',
    ...overrides,
  }
}

describe('planetMarkYearEvidenceHelpers', () => {
  it('filters year report evidence to measurement report and certificate types', () => {
    const rows = filterYearReportEvidence([
      evidence({ document_type: 'measurement_report' }),
      evidence({ id: 2, document_type: 'planet_mark_certificate' }),
      evidence({ id: 3, document_type: 'utility_bill' }),
    ])
    expect(rows).toHaveLength(2)
    expect(rows.map((row) => row.document_type)).toEqual([
      'measurement_report',
      'planet_mark_certificate',
    ])
  })

  it('builds multipart form data for certification uploads', () => {
    const file = new File(['pdf'], 'Measurement Report.pdf', { type: 'application/pdf' })
    const formData = buildYearEvidenceUploadFormData(
      file,
      PLANET_MARK_YEAR_CERT_DOC_TYPES.measurementReport,
    )
    expect(formData.get('document_type')).toBe('measurement_report')
    expect(formData.get('evidence_category')).toBe('certification')
    expect(formData.get('document_name')).toBe('Measurement Report.pdf')
  })

  it('validates unsupported mime types and oversized files', () => {
    const big = new File([new ArrayBuffer(21 * 1024 * 1024)], 'big.pdf', {
      type: 'application/pdf',
    })
    expect(validateYearEvidenceFile(big)).toMatch(/20 MB/)

    const badType = new File(['x'], 'notes.txt', { type: 'text/plain' })
    expect(validateYearEvidenceFile(badType)).toMatch(/not supported/)
  })

  it('formats evidence file sizes', () => {
    expect(formatEvidenceFileSizeKb(450)).toBe('450 KB')
    expect(formatEvidenceFileSizeKb(2048)).toBe('2.0 MB')
    expect(formatEvidenceFileSizeKb(null)).toBe('—')
  })

  it('maps document type label keys', () => {
    expect(isPlanetMarkYearCertDocType('measurement_report')).toBe(true)
    expect(yearEvidenceDocumentTypeLabelKey('planet_mark_certificate')).toBe(
      'planet_mark.shell.years.evidence.type.planet_mark_certificate',
    )
  })

  it('detects retryable API errors', () => {
    expect(isRetryableYearEvidenceError({ response: { status: 503 } })).toBe(true)
    expect(isRetryableYearEvidenceError({ code: 'ECONNABORTED' })).toBe(true)
    expect(isRetryableYearEvidenceError({ response: { status: 400 } })).toBe(false)
  })
})
